from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from session_manager import end_chat_session, is_in_chat, get_partner
from saveNload import add_user_block
from message import NOT_IN_CHAT_TEXT

import init


@check_user_profile
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Blocks the user's current chat partner.
    Severs the chat session and guarantees neither user will ever be matched again.
    """
    user_id = update.effective_user.id

    if not is_in_chat(user_id):
        # Check if there is a recent partner to block
        recent = init.recent_partners.get(user_id, [])
        if recent:
            target_id = recent[-1]
            await add_user_block(user_id, target_id)
            await safe_tele_func_call(
                update.message.reply_text,
                text="🚫 <b>User blocked.</b> You will not be paired with them for the next 24 hours.",
                parse_mode="HTML"
            )
            return
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return

    partner_id = get_partner(user_id)
    if partner_id:
        # Record 24-hour block in DB
        await add_user_block(user_id, partner_id)

        # Sever session
        await end_chat_session(
            context,
            user_id,
            reason="blocked",
            notify_initiator=False,
            notify_partner=True,
        )

        await safe_tele_func_call(
            update.message.reply_text,
            text="🚫 <b>Partner blocked.</b> This chat is ended and you will not be matched with them for the next 24 hours.",
            parse_mode="HTML"
        )
