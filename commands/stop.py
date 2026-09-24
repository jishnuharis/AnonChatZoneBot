from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from session_manager import end_chat_session, is_in_chat
from message import REMOVED_FROM_QUEUE_TEXT, NOT_IN_CHAT_TEXT

import init


@check_user_profile
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_in_chat(user_id):
        # Gracefully end session using unified session manager
        await end_chat_session(
            context,
            user_id,
            reason="user_stopped",
            notify_initiator=True,
            notify_partner=True,
        )
    elif user_id in init.waiting_users:
        async with init.queue_lock:
            if user_id in init.waiting_users:
                init.waiting_users.remove(user_id)
            init.wait_started.pop(user_id, None)
        await safe_tele_func_call(update.message.reply_text, text=REMOVED_FROM_QUEUE_TEXT, parse_mode="HTML")
    else:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
