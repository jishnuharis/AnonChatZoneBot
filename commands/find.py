from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from matchmaking import enqueue_and_match
from message import ALREADY_IN_CHAT_TEXT, LOOKING_FOR_PARTNER_TEXT

from subscription import has_daily_credit, consume_daily_credit, daily_credit_limit
from message import DAILY_NEXT_LIMIT_REACHED_TEXT

import init


@check_user_profile
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE, charge: bool = True):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:
        await safe_tele_func_call(update.message.reply_text, text=ALREADY_IN_CHAT_TEXT, parse_mode="HTML")
        return

    if charge and user_id not in init.waiting_users:
        if not has_daily_credit(user_id):
            await safe_tele_func_call(
                update.message.reply_text,
                text=DAILY_NEXT_LIMIT_REACHED_TEXT.format(limit=daily_credit_limit(user_id)),
                parse_mode="HTML",
            )
        consume_daily_credit(user_id)

    if user_id not in init.waiting_users:
        await safe_tele_func_call(update.message.reply_text, text=LOOKING_FOR_PARTNER_TEXT, parse_mode="HTML")

    await enqueue_and_match(context, user_id)
