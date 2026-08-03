import random
import time
from html import escape as esc

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from security import safe_tele_func_call
from saveNload import save_config
import subscription

import init

# The reward is always a subscription of this tier, granted every time an
# inviter crosses another multiple of the scheme's required_referrals - the
# admin only configures the threshold and how long the promo itself runs
# (see set_scheme), not the reward's size or length.
REWARD_TIER = "weekly"

# 1-in-this-many chance the referral scheme gets mentioned after a chat ends
# (see maybe_announce, called from handlers/rating.py).
ANNOUNCE_CHANCE = 1 / 20


def scheme_active() -> bool:
    """Whether a referral promo is currently running. A scheme is active
    only while BOTH required_referrals is a real threshold (>=1) AND the
    promo hasn't passed its own expiry - admins set both at once via
    /referral and the promo auto-expires on its own, no sweep job needed
    since this is only ever checked lazily (mirrors subscription.is_subscribed)."""
    scheme = init.referral_scheme
    required = scheme.get("required_referrals") or 0
    expires = scheme.get("expires")
    return required >= 1 and bool(expires) and expires > time.time()


def set_scheme(required_referrals: int, duration_days: int) -> dict:
    """Admin entry point (see commands/admin_commands.py /referral). Turns the
    scheme off if required_referrals is -1, duration_days is <= 0, or both -
    any of the three disables it. Otherwise (re)activates it for duration_days,
    replacing whatever was configured before. Persisted immediately, not
    batched, since admin config changes are rare and should apply right away."""
    if required_referrals == -1 or duration_days <= 0:
        init.referral_scheme = {"required_referrals": 0, "expires": None}
    else:
        init.referral_scheme = {
            "required_referrals": required_referrals,
            "expires": time.time() + duration_days * 86400,
        }
    save_config("referral_scheme", init.referral_scheme)
    return init.referral_scheme


def referral_link(bot_username: str, user_id: int) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def capture_referral(context, user_id: int):
    """Called the moment a brand-new user's row is created (see
    handlers/setup.py). If they arrived via a /start ref_<inviter_id> deep
    link, remembers who invited them - once, forever. Never overwritten, and
    never credited here; crediting only happens once they actually finish
    onboarding (see credit_referral), so a link tap alone earns nothing."""
    args = context.args
    if not args or not args[0].startswith("ref_"):
        return
    try:
        inviter_id = int(args[0][len("ref_"):])
    except ValueError:
        return
    if inviter_id == user_id or inviter_id not in init.user_details:
        return
    init.user_details[user_id]["referred_by"] = inviter_id
    init.dirty_users.add(user_id)


async def credit_referral(context, user_id: int):
    """Called once a new user finishes onboarding (gender+age+country all
    set - see handlers/country.py). If they were referred, credits their
    inviter's referral_count and, once the inviter has enough *unrewarded*
    referrals to clear the scheme's current threshold, grants them a REWARD_TIER
    subscription and notifies them. Rewards stack (extend, don't overwrite) on
    top of any existing subscription, same as admin grants and purchases.

    Referrals are only ever rewarded while the scheme is active at the moment
    the threshold is crossed - but referral_count itself always increments
    regardless, so nobody's referral is "lost" if the promo happens to be off;
    it just won't pay out until (if) an admin reactivates the scheme and the
    inviter's unrewarded count clears the new threshold."""
    details = init.user_details.get(user_id)
    if not details or details.get("referral_credited") or not details.get("referred_by"):
        return

    inviter_id = details["referred_by"]
    inviter = init.user_details.get(inviter_id)
    if not inviter:
        return

    details["referral_credited"] = True
    inviter["referral_count"] = inviter.get("referral_count", 0) + 1
    init.dirty_users.update([user_id, inviter_id])

    if not scheme_active():
        return

    required = init.referral_scheme["required_referrals"]
    unrewarded = inviter["referral_count"] - inviter.get("referral_rewarded_count", 0)
    if unrewarded < required:
        return

    inviter["referral_rewarded_count"] = inviter.get("referral_rewarded_count", 0) + required
    init.dirty_users.add(inviter_id)

    tier = subscription.TIERS[REWARD_TIER]
    new_expiry = subscription.grant_subscription(inviter_id, REWARD_TIER, source="referral")
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(new_expiry))

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=inviter_id,
        text=(
            f"🎉 <b>Referral reward unlocked!</b>\n"
            f"<i>You've referred {required} more friends who joined and finished setting up their profile.</i>\n"
            f"<i>+{tier['label']} subscription granted, active until</i> <code>{expires_str}</code> "
            f"<i>(+{tier['bonus_points']} points too) 🎁</i>"
        ),
        parse_mode="HTML",
    )


def _link_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Get my referral link", callback_data="refgen")]])


async def maybe_announce(bot, user_id: int):
    """Called right after a chat ends (see handlers/rating.py). About 1 in 20
    times, and only while a scheme is actually running, nudges the user
    towards the referral program alongside the usual rate/report prompt."""
    if not scheme_active() or random.random() >= ANNOUNCE_CHANCE:
        return

    required = init.referral_scheme["required_referrals"]
    tier = subscription.TIERS[REWARD_TIER]
    await safe_tele_func_call(
        bot.send_message,
        chat_id=user_id,
        text=(
            f"🎁 <b>Referral bonus is live right now!</b>\n"
            f"<i>Refer {required} friends who join and finish setting up their profile, and you'll get a free "
            f"{tier['label']} subscription — repeatable every {required} referrals, for as long as the promo runs.</i>"
        ),
        reply_markup=_link_keyboard(),
        parse_mode="HTML",
    )


async def handle_referral_link_button(update, context):
    """Callback for the 🔗 button, whether it came from /profile or a
    maybe_announce nudge - both just show the same link + progress card."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id not in init.user_details:
        return

    link = referral_link(context.bot.username, user_id)
    details = init.user_details[user_id]
    count = details.get("referral_count", 0)
    rewarded = details.get("referral_rewarded_count", 0)

    progress_line = ""
    if scheme_active():
        required = init.referral_scheme["required_referrals"]
        toward_next = (count - rewarded) % required
        progress_line = f"\n<i>Progress toward your next reward:</i> {toward_next}/{required}"
    elif count:
        progress_line = "\n<i>No promo running right now - your count is saved for whenever one starts.</i>"

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=user_id,
        text=(
            f"🔗 <b>Your referral link:</b>\n<code>{esc(link)}</code>\n\n"
            f"<i>Share it - when someone joins through it and finishes setting up their profile, it counts.</i>\n"
            f"<i>Total successful referrals:</i> {count}{progress_line}"
        ),
        parse_mode="HTML",
    )
