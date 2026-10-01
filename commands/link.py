import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call
from subscription import is_subscribed
from message import (
    NOT_IN_CHAT_USE_FIND_INLINE_TEXT,
    LINK_COMMAND_WARMUP_LOCKED_TEXT,
    LINK_NO_USERNAME_TEXT,
    LINK_SENT_TO_PARTNER_ALERT,
    LINK_SENT_SUCCESS_TEXT,
)


async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Allows a user in an active chat session to safely share their Telegram profile
    with their partner as an inline URL button, keeping their raw username hidden
    from chat logs and preventing link-spam bypasses.
    
    Free tier users are subject to a 1-minute warm-up lock from the start of the chat.
    Subscribed (VIP) users can share immediately.
    """
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id

    # 1. Must be in an active chat
    if user_id not in init.active_pairs:
        await safe_tele_func_call(
            update.message.reply_text,
            text=NOT_IN_CHAT_USE_FIND_INLINE_TEXT,
            parse_mode="HTML",
        )
        return

    # 2. Free tier 1-minute warmup lock
    if not is_subscribed(user_id):
        session_start = init.session_start_times.get(user_id, time.time())
        elapsed = time.time() - session_start
        if elapsed < 60:
            remaining = max(1, int(60 - elapsed))
            await safe_tele_func_call(
                update.message.reply_text,
                text=LINK_COMMAND_WARMUP_LOCKED_TEXT.format(remaining=remaining),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ Get VIP / Subscribe", callback_data="sub|upgrade_prompt")]
                ]),
                parse_mode="HTML",
            )
            return

    # 3. User must have a Telegram username
    username = update.effective_user.username
    if not username:
        await safe_tele_func_call(
            update.message.reply_text,
            text=LINK_NO_USERNAME_TEXT,
            parse_mode="HTML",
        )
        return

    partner_id = init.active_pairs[user_id]
    partner_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 View Profile", url=f"https://t.me/{username}")]
    ])

    sent = await safe_tele_func_call(
        context.bot.send_message,
        chat_id=partner_id,
        text=LINK_SENT_TO_PARTNER_ALERT,
        reply_markup=partner_keyboard,
        parse_mode="HTML",
    )

    if sent:
        await safe_tele_func_call(
            update.message.reply_text,
            text=LINK_SENT_SUCCESS_TEXT,
            parse_mode="HTML",
        )

        # Ephemeral transcript recording
        session_id = init.active_sessions.get(user_id)
        if session_id:
            buf = init.session_messages.setdefault(session_id, [])
            buf.append((user_id, "[SHARED PROFILE LINK BUTTON]", time.time()))
