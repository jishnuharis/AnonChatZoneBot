import random
import time
from html import escape as esc

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from security import safe_tele_func_call
from saveNload import save_config
import subscription

import init

REWARD_TIER = "weekly"

ANNOUNCE_CHANCE = 1 / 20


def scheme_active() -> bool:
    scheme = init.referral_scheme
    required = scheme.get("required_referrals") or 0
    expires = scheme.get("expires")
    return required >= 1 and bool(expires) and expires > time.time()


def set_scheme(required_referrals: int, duration_days: int) -> dict:
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
