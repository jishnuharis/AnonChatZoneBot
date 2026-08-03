from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from html import escape as esc

from handlers.setup import check_user_profile
from handlers.preferences import describe_preferences
from security import safe_tele_func_call
import subscription

import init


def _profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Gender", callback_data="edit|gender"),
         InlineKeyboardButton("✏️ Edit Age", callback_data="edit|age")],
        [InlineKeyboardButton("✏️ Edit Country", callback_data="edit|country"),
         InlineKeyboardButton("🏷️ Edit Interests", callback_data="edit|preferences")],
        [InlineKeyboardButton("🔗 My Referral Link", callback_data="refgen")],
    ])


async def _build_profile_text(user_id, context: ContextTypes.DEFAULT_TYPE, fallback_name=None, fallback_username=None):
    user = init.user_details.get(user_id)
    if not user:
        return None

    full_name, username = fallback_name, fallback_username
    if full_name is None:
        chat = await safe_tele_func_call(context.bot.get_chat, user_id)
        full_name = esc(chat.full_name) if chat and chat.full_name else "Unknown"
        username = chat.username if chat else None
    else:
        full_name = esc(full_name)

    username_line = f" | @{esc(username)}" if username else ""
    votes = user.get("votes", {"up": 0, "down": 0})
    prefs_text = esc(describe_preferences(user.get("preferences", 0)))

    return (
        "<b>👤 Your Profile</b>\n\n"
        f"<b>Name:</b> {full_name}{username_line}\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Gender:</b> {'Male' if user['gender'] == 'M' else 'Female'}\n"
        f"<b>Age:</b> {user['age']}\n"
        f"<b>Country:</b> {esc(str(user['country']))}\n"
        f"<b>Interests:</b> {prefs_text}\n"
        f"<b>Rating:</b> {votes['up']} 👍 {votes['down']} 👎\n"
        f"<b>Points:</b> {user['points']}\n\n"
        f"{subscription.status_text(user_id)}"
    )


@check_user_profile
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = await _build_profile_text(
        user_id, context,
        fallback_name=update.effective_user.full_name,
        fallback_username=update.effective_user.username,
    )
    await safe_tele_func_call(update.message.reply_text, text=text, reply_markup=_profile_keyboard(), parse_mode="HTML")


async def send_profile_menu(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    text = await _build_profile_text(user_id, context)
    if not text:
        return
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=text, reply_markup=_profile_keyboard(), parse_mode="HTML")
