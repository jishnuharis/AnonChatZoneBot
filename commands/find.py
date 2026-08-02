# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call
from matchmaking import enqueue_and_match
from message import ALREADY_IN_CHAT_TEXT, LOOKING_FOR_PARTNER_TEXT

from subscription import has_daily_credit, consume_daily_credit, daily_credit_limit
from message import DAILY_NEXT_LIMIT_REACHED_TEXT

import init  # Importing the bot credentials and users' details


# Function which pushes the user's ID into waiting_users list to find a partner later on
@check_user_profile
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE, charge: bool = True):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:  # Checks if the user is already in a chat and notifies if they are in a chat already
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

    if user_id not in init.waiting_users:  # Notifies the user that we're searching
        await safe_tele_func_call(update.message.reply_text, text=LOOKING_FOR_PARTNER_TEXT, parse_mode="HTML")

    await enqueue_and_match(context, user_id)  # Adds them to the queue and tries an interest-based match right away
