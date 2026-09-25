from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
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
    Prompts the user with a confirmation dialog before blocking.
    """
    user_id = update.effective_user.id

    if is_in_chat(user_id):
        partner_id = get_partner(user_id)
        if partner_id:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚫 Yes, Block Partner", callback_data=f"block_confirm|{partner_id}|active"),
                    InlineKeyboardButton("❌ Cancel", callback_data="block_cancel"),
                ]
            ])
            await safe_tele_func_call(
                update.message.reply_text,
                text=(
                    "⚠️ <b>Are you sure you want to block your current partner?</b>\n\n"
                    "• This chat will immediately end.\n"
                    "• Neither of you will match with each other for the next 24 hours."
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return

    # Check if there is a recent partner to block
    recent = init.recent_partners.get(user_id, [])
    if recent:
        target_id = recent[-1]
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Yes, Block User", callback_data=f"block_confirm|{target_id}|recent"),
                InlineKeyboardButton("❌ Cancel", callback_data="block_cancel"),
            ]
        ])
        await safe_tele_func_call(
            update.message.reply_text,
            text=(
                "⚠️ <b>Are you sure you want to block your previous partner?</b>\n\n"
                "• Neither of you will match with each other for the next 24 hours."
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")


async def handle_block_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles confirmation or cancellation of blocking."""
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]
    user_id = update.effective_user.id

    if action == "block_cancel":
        await safe_tele_func_call(
            query.edit_message_text,
            text="❌ <i>Block cancelled. Chat remains unaffected.</i>",
            parse_mode="HTML"
        )
        return

    if action == "block_confirm":
        if len(data) < 3:
            return
        target_id = int(data[1])
        mode = data[2]

        await add_user_block(user_id, target_id)

        if mode == "active":
            # If still connected with this partner, sever the chat
            current_partner = get_partner(user_id)
            if current_partner == target_id:
                await end_chat_session(
                    context,
                    user_id,
                    reason="blocked",
                    notify_initiator=False,
                    notify_partner=True,
                )
            await safe_tele_func_call(
                query.edit_message_text,
                text="🚫 <b>Partner blocked.</b> Chat ended. You will not be matched with them for the next 24 hours.",
                parse_mode="HTML"
            )
        else:
            await safe_tele_func_call(
                query.edit_message_text,
                text="🚫 <b>User blocked.</b> You will not be paired with them for the next 24 hours.",
                parse_mode="HTML"
            )
