from telegram import Update
from telegram.ext import ContextTypes
from html import escape as esc
import asyncio
import time

from security import safe_tele_func_call, format_duration
from handlers.rating import ask_for_rating
from games.registry import end_any_active_game
from moderation import is_admin, apply_restriction, clear_restriction
from message import (
    GIVE_BROADCAST_MESSAGE_TEXT, GIVE_VALID_CONNECT_USER_ID_TEXT, TARGET_NOT_IN_DB_TEXT,
    ALREADY_CONNECTED_TO_TARGET_TEXT, PARTNER_LEFT_CHAT_TEXT, ADMIN_HELP_TEXT, BAN_USAGE_TEXT,
    SEVERITY_RANGE_TEXT, CANT_RESTRICT_SELF_TEXT, ADMINS_CANT_BE_RESTRICTED_TEXT,
    SEVERITY_ZERO_NOOP_TEXT, UNBAN_USAGE_TEXT, GIVE_VALID_USER_ID_TEXT, RESTRICTION_LIFTED_TEXT,
    CHECKUSER_USAGE_TEXT, NO_RECORD_OF_USER_TEXT, NOT_RESTRICTED_TEXT, NO_REPORTS_TEXT,
    GIVEAWAY_USAGE_TEXT, GIVEAWAY_UNKNOWN_TIER_TEXT,
)
import subscription

import init


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    message = update.message.text
    if message.lower().startswith("/broadcast"):
        message = message[len("/broadcast"):].lstrip()

    if not message:
        await update.message.reply_text(GIVE_BROADCAST_MESSAGE_TEXT, parse_mode="HTML")
        return

    sent = 0
    for user_id in init.user_details:
        try:
            await safe_tele_func_call(
                context.bot.send_message,
                chat_id=user_id,
                text=message,
            )
            sent += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")

    await update.message.reply_text(f"<i>Broadcast sent to</i> <b>{sent}</b> <i>users ✅.</i>", parse_mode="HTML")


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    message = update.message.text
    if message.lower().startswith("/connect"):
        message = message[len("/connect"):].strip()
    try:
        target_id = int(message)
    except ValueError:
        await update.message.reply_text(GIVE_VALID_CONNECT_USER_ID_TEXT, parse_mode="HTML")
        return

    if target_id not in init.user_details:
        await update.message.reply_text(TARGET_NOT_IN_DB_TEXT, parse_mode="HTML")
        return

    if target_id == init.user_details[user_id]["partner_id"]:
        await update.message.reply_text(ALREADY_CONNECTED_TO_TARGET_TEXT, parse_mode="HTML")
        return

    targets_partner = init.user_details[target_id]["partner_id"]
    if targets_partner:
        init.active_pairs.pop(targets_partner, None)
        init.active_pairs.pop(target_id, None)
        init.message_map.pop(targets_partner, None)
        init.message_map.pop(target_id, None)
        init.user_details[targets_partner]["partner_id"] = None
        await end_any_active_game(context, targets_partner)
        await end_any_active_game(context, target_id)

        await safe_tele_func_call(context.bot.send_message, chat_id=targets_partner, text=PARTNER_LEFT_CHAT_TEXT, parse_mode="HTML")
        await ask_for_rating(context.bot, targets_partner, target_id)

    users_partner = init.user_details[user_id]["partner_id"]
    if users_partner:
        init.active_pairs.pop(users_partner, None)
        init.active_pairs.pop(user_id, None)
        init.message_map.pop(users_partner, None)
        init.message_map.pop(user_id, None)
        init.user_details[users_partner]["partner_id"] = None
        await end_any_active_game(context, users_partner)
        await end_any_active_game(context, user_id)

        await safe_tele_func_call(context.bot.send_message, chat_id=users_partner, text=PARTNER_LEFT_CHAT_TEXT, parse_mode="HTML")
        await ask_for_rating(context.bot, users_partner, user_id)

    init.active_pairs[user_id] = target_id
    init.active_pairs[target_id] = user_id
    uv1, uv2 = init.user_details[user_id]["votes"], init.user_details[target_id]["votes"]
    init.user_details[user_id]["partner_id"] = target_id
    init.user_details[target_id]["partner_id"] = user_id
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=f"🎯 <b>Found user.... Say hi!!</b>\n<i>Rating:</i> {uv2['up']} 👍 {uv2['down']} 👎\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=f"🎯 <b>Someone found you.... Say hi!!</b>\n<i>Rating:</i> {uv1['up']} 👍 {uv1['down']} 👎\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>", parse_mode="HTML")

    init.dirty_users.update([user_id, target_id])


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(ADMIN_HELP_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
        severity = int(args[1])
    except ValueError:
        await update.message.reply_text(BAN_USAGE_TEXT, parse_mode="HTML")
        return

    if not (0 <= severity <= 10):
        await update.message.reply_text(SEVERITY_RANGE_TEXT, parse_mode="HTML")
        return

    # Admins (including the owner) can never be restricted through this bot -
    # not by themselves, not by another admin, not automatically. Catch the
    # self-ban case here with an explicit message rather than letting it
    # silently no-op through apply_restriction.
    if target_id == user_id:
        await update.message.reply_text(CANT_RESTRICT_SELF_TEXT, parse_mode="HTML")
        return
    if is_admin(target_id):
        await update.message.reply_text(ADMINS_CANT_BE_RESTRICTED_TEXT, parse_mode="HTML")
        return

    reason = " ".join(args[2:]) if len(args) > 2 else "Manual admin action"

    until = apply_restriction(target_id, severity, reason)
    if not until:
        await update.message.reply_text(SEVERITY_ZERO_NOOP_TEXT, parse_mode="HTML")
        return

    remaining = format_duration(until - time.time())
    await update.message.reply_text(f"⛔ <i>User</i> <code>{target_id}</code> <i>restricted for</i> <b>{esc(remaining)}</b> <i>(severity {severity}).</i>\n<i>Reason:</i> <code>{esc(reason)}</code>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=f"⛔ <b>You've been restricted by an admin.</b>\n<i>Reason:</i> <code>{esc(reason)}</code>\n<i>Time:</i> <code>{esc(remaining)}</code>", parse_mode="HTML")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(UNBAN_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    clear_restriction(target_id)
    await update.message.reply_text(f"✅ <i>User</i> <code>{target_id}</code> <i>has been unrestricted.</i>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=RESTRICTION_LIFTED_TEXT, parse_mode="HTML")


async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(CHECKUSER_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    details = init.user_details.get(target_id)
    if not details:
        await update.message.reply_text(NO_RECORD_OF_USER_TEXT, parse_mode="HTML")
        return

    restricted_until = details.get("restricted_until")
    if restricted_until and restricted_until > time.time():
        restriction_line = f"⛔ Restricted for {format_duration(restricted_until - time.time())} — <code>{esc(str(details.get('restriction_reason')))}</code>"
    else:
        restriction_line = NOT_RESTRICTED_TEXT

    recent_reports = details.get("report_log", [])[-5:]
    reports_text = "\n".join(
        f"  • <code>{esc(str(r['reason']))}</code> from <code>{r['reporter']}</code>" for r in recent_reports
    ) or NO_REPORTS_TEXT

    text = (
        f"<b>User</b> <code>{target_id}</code>\n"
        f"Points: {details.get('points', 0)}\n"
        f"Votes: {details.get('votes', {}).get('up', 0)} 👍 {details.get('votes', {}).get('down', 0)} 👎\n"
        f"Severity score: {details.get('severity_score', 0)}\n"
        f"{restriction_line}\n"
        f"Recent reports:\n{reports_text}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def giveaway_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/giveaway <user_id> <tier> - manually grants a subscription tier, same
    perks and bonus points a paid purchase of that tier would give. Stacks
    with (extends from) any existing active subscription rather than
    overwriting it."""
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(GIVEAWAY_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    tier_key = args[1].lower()
    if tier_key not in subscription.TIERS:
        await update.message.reply_text(GIVEAWAY_UNKNOWN_TIER_TEXT, parse_mode="HTML")
        return

    if target_id not in init.user_details:
        await update.message.reply_text(TARGET_NOT_IN_DB_TEXT, parse_mode="HTML")
        return

    tier = subscription.TIERS[tier_key]
    new_expiry = subscription.grant_subscription(target_id, tier_key, source="admin_grant")
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(new_expiry))

    await update.message.reply_text(
        f"✅ <i>Granted</i> <b>{tier['label']}</b> <i>to</i> <code>{target_id}</code> "
        f"<i>(+{tier['bonus_points']} points). Active until</i> <code>{expires_str}</code>.",
        parse_mode="HTML",
    )
    await safe_tele_func_call(
        context.bot.send_message, chat_id=target_id,
        text=(
            f"🎁 <b>An admin gifted you a {tier['label']} subscription!</b>\n"
            f"<i>Active until:</i> <code>{expires_str}</code>\n"
            f"<i>+{tier['bonus_points']} points added 🎉</i>"
        ),
        parse_mode="HTML",
    )
