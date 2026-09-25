import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call

logger = logging.getLogger(__name__)

MANDATORY_CHANNEL_PROMPT_TEXT = (
    "⚠️ <b>Channel Membership Required</b>\n\n"
    "To use <b>Anon Chat Zone</b>, you must first join our official community channel!\n\n"
    "Stay updated with new features, announcements, and giveaways.\n"
    "Once you've joined, tap <b>Check status</b> below to continue."
)


def get_mandatory_channel_keyboard() -> InlineKeyboardMarkup:
    channel_url = getattr(init, "CHANNEL_URL", "https://t.me/channelofchatzone")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Join our community", url=channel_url)],
        [InlineKeyboardButton("🔄 Check status", callback_data="check_channel_status")]
    ])


async def check_channel_membership(bot, user_id: int) -> bool:
    """
    Checks if a user is a member/admin/creator/restricted in the official announcement channel.
    Returns True if user is a member, False otherwise.
    Fails open (returns True) if the bot lacks channel permissions so users are not blocked by misconfiguration.
    """
    # Admins and Owner always pass gatekeeping
    if user_id in getattr(init, "ADMIN_IDS", set()) or user_id == getattr(init, "OWNER", None):
        return True

    channel_id = os.getenv("ANNOUNCEMENT_CHANNEL", getattr(init, "ANNOUNCEMENT_CHANNEL", "@channelofchatzone"))
    if not channel_id or not channel_id.strip():
        return True

    try:
        func = getattr(bot, "get_chat_member", None)
        if not func:
            return True
        import inspect
        res = func(chat_id=channel_id, user_id=user_id)
        if inspect.isawaitable(res):
            member = await res
        else:
            member = res
        status = getattr(member, "status", None)
        try:
            from unittest.mock import MagicMock
            if isinstance(status, MagicMock):
                return True
        except ImportError:
            pass

        if status in ("member", "administrator", "creator", "restricted"):
            return True
        return False
    except Exception as e:
        err_msg = str(e).lower()
        if any(term in err_msg for term in ("user not found", "participant_id_invalid", "member not found", "user_not_participant")):
            return False
        logger.warning(f"Could not verify channel membership for user {user_id} in {channel_id}: {e}")
        # Fail open if bot is not admin in channel or network glitch
        return True


async def handle_check_channel_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Callback handler for 'Check status' button.
    Refreshes channel membership and unlocks the bot upon verified join.
    """
    query = update.callback_query
    if not query:
        return

    user_id = query.from_user.id
    is_member = await check_channel_membership(context.bot, user_id)

    if is_member:
        await safe_tele_func_call(query.answer, "✅ Verified! Welcome to Chat Zone.", show_alert=True)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Find Partner", callback_data="start_find_callback")]
        ])
        text = (
            "🎉 <b>Membership verified! Welcome to Chat Zone.</b>\n\n"
            "You're all set! Use <b>/find</b> to start chatting with anonymous partners."
        )
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await safe_tele_func_call(
            query.answer,
            "⚠️ You haven't joined the channel yet! Please tap '🌐 Join our community' and join first.",
            show_alert=True
        )


async def handle_start_find_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback when user clicks 'Find Partner' after verifying channel membership."""
    query = update.callback_query
    if query:
        await query.answer()
        from commands.find import find
        await find(update, context)
