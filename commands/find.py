from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_reply, format_duration
from matchmaking import enqueue_and_match
from moderation import is_user_restricted
from message import ALREADY_IN_CHAT_TEXT, LOOKING_FOR_PARTNER_TEXT
from subscription import has_daily_credit, consume_daily_credit, daily_credit_limit
from message import DAILY_NEXT_LIMIT_REACHED_TEXT

import init


@check_user_profile
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE, charge: bool = False):
    user_id = update.effective_user.id

    # Layer 1: Strict Ban & Restriction check
    restricted, reason, remaining = is_user_restricted(user_id)
    if restricted:
        remaining_str = format_duration(remaining or 0)
        await safe_reply(
            update,
            text=f"⛔ <b>You are restricted from matchmaking.</b>\n<i>Reason:</i> <code>{reason}</code>\n<i>Time left:</i> <code>{remaining_str}</code>",
            context=context,
        )
        return

    # Check already in chat
    if user_id in init.active_pairs:
        await safe_reply(update, text=ALREADY_IN_CHAT_TEXT, context=context)
        return

    # Credit deduction (e.g. when called via /next)
    if charge and user_id not in init.waiting_users:
        if not has_daily_credit(user_id):
            await safe_reply(
                update,
                text=DAILY_NEXT_LIMIT_REACHED_TEXT.format(limit=daily_credit_limit(user_id)),
                context=context,
            )
            return  # Fixed: return immediately when out of credits!
        consume_daily_credit(user_id)

    if user_id not in init.waiting_users:
        await safe_reply(update, text=LOOKING_FOR_PARTNER_TEXT, context=context)

    await enqueue_and_match(context, user_id)
