import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from commands.find import find
from handlers.setup import check_user_profile
from security import safe_tele_func_call, safe_reply
from session_manager import end_chat_session, is_in_chat, start_chat_session, IN_CHAT_KEYBOARD
from matchmaking import dequeue_user
from message import PARTNER_SKIPPED_TEXT, NOT_IN_CHAT_USE_FIND_TEXT

from group_helper import is_group_chat, reply_group_redirect
import init


@check_user_profile
async def skip_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_group_chat(update):
        return await reply_group_redirect(update, context, start_arg="find")

    user_id = update.effective_user.id

    if is_in_chat(user_id):
        try:
            from streaks import record_chat_interaction
            record_chat_interaction(user_id, bot=getattr(context, "bot", None))
        except Exception as e:
            pass

        # Gracefully end session using unified session manager with full Chat Options
        await end_chat_session(
            context,
            user_id,
            reason="skipped",
            notify_initiator=True,
            notify_partner=True,
        )

        await find(update, context, charge=True)
    else:
        await find(update, context, charge=True)


async def handle_undo_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    data = query.data or ""
    parts = data.split("|")
    if len(parts) < 2:
        return

    try:
        partner_id = int(parts[1])
    except ValueError:
        return

    skip_info = init.recent_skips.get(user_id)
    if not skip_info or skip_info[0] != partner_id:
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>No active skip to undo.</b>",
            parse_mode="HTML",
        )
        return

    _, skip_ts = skip_info
    if time.time() - skip_ts > 60:
        init.recent_skips.pop(user_id, None)
        await safe_tele_func_call(
            query.edit_message_text,
            text="⏳ <b>Undo window expired (60s limit).</b>",
            parse_mode="HTML",
        )
        return

    if is_in_chat(user_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>You are already in a chat with someone else.</b>",
            parse_mode="HTML",
        )
        return

    if is_in_chat(partner_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>Your previous partner has already matched with someone else.</b>",
            parse_mode="HTML",
        )
        return

    # Dequeue both from waiting queues if they were searching
    await dequeue_user(user_id)
    await dequeue_user(partner_id)

    success = await start_chat_session(context, user_id, partner_id)
    if success:
        init.recent_skips.pop(user_id, None)
        await safe_tele_func_call(
            query.edit_message_text,
            text="🔄 <b>Chat reconnected! You are back with your partner.</b>",
            parse_mode="HTML",
        )
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=partner_id,
            text="🔄 <b>Your partner reconnected the chat! You are back together.</b>",
            parse_mode="HTML",
            reply_markup=IN_CHAT_KEYBOARD,
        )
    else:
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>Could not reconnect. The partner may be unavailable.</b>",
            parse_mode="HTML",
        )
