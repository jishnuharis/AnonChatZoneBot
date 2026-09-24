from telegram import Update
from telegram.ext import ContextTypes

from commands.find import find
from handlers.setup import check_user_profile
from security import safe_tele_func_call
from session_manager import end_chat_session, is_in_chat
from message import PARTNER_SKIPPED_TEXT, NOT_IN_CHAT_USE_FIND_TEXT

import init


@check_user_profile
async def skip_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_in_chat(user_id):
        # Gracefully end session using unified session manager
        await end_chat_session(
            context,
            user_id,
            reason="skipped",
            notify_initiator=False,
            notify_partner=True,
        )

        await safe_tele_func_call(update.message.reply_text, text=PARTNER_SKIPPED_TEXT, parse_mode="HTML")
        await find(update, context, charge=True)
    else:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_USE_FIND_TEXT, parse_mode="HTML")
