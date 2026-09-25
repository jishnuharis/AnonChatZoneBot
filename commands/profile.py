from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from html import escape as esc

from handlers.setup import check_user_profile
from handlers.preferences import describe_preferences
from security import safe_tele_func_call
from saveNload import get_user_votes
import subscription

import init


def _profile_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Anonymous Friends List", callback_data="flist|0")],
        [InlineKeyboardButton("✏️ Edit Gender", callback_data="edit|gender"),
         InlineKeyboardButton("✏️ Edit Age", callback_data="edit|age")],
        [InlineKeyboardButton("✏️ Edit Country", callback_data="edit|country"),
         InlineKeyboardButton("🏷️ Edit Interests", callback_data="edit|preferences")],
        [InlineKeyboardButton("⭐ Match Filters (Gender/Country)", callback_data="edit|match_filters")],
        [InlineKeyboardButton("🔗 My Referral Link", callback_data="refgen")],
        [InlineKeyboardButton("💬 Community Group", url=init.GROUP_URL)],
    ])


async def _build_profile_text(user_id, context: ContextTypes.DEFAULT_TYPE, fallback_name=None, fallback_username=None):
    if user_id not in init.user_details:
        await init.ensure_user_loaded(user_id)
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
    
    # Query fresh live votes from database / cache
    votes = await get_user_votes(user_id)
    user["votes"] = votes
    up_votes = votes.get("up", 0) if isinstance(votes, dict) else 0
    down_votes = votes.get("down", 0) if isinstance(votes, dict) else 0

    prefs_text = esc(describe_preferences(user.get("preferences", 0)))

    pref_g = user.get("pref_gender", "ANY")
    pref_c = user.get("pref_country", "ANY")
    g_map = {"ANY": "Any", "M": "Male Only", "F": "Female Only"}
    c_map = {"ANY": "Any", "SAME": f"Same Country ({user.get('country')})"}
    filter_line = f"<b>Match Filters:</b> {g_map.get(pref_g, pref_g)} | {c_map.get(pref_c, pref_c)}\n" if subscription.is_subscribed(user_id) else ""

    streak = user.get("current_streak", 0) or 0
    longest = user.get("longest_streak", 0) or 0
    from streaks import get_next_streak_milestone
    next_day, next_rew = get_next_streak_milestone(streak)
    next_info = f" <i>(Next: {next_day}d ➔ {next_rew['label']})</i>" if next_day else ""
    streak_line = f"🔥 <b>Chat Streak:</b> {streak} day{'s' if streak != 1 else ''} <i>(Best: {longest}d)</i>{next_info}\n"

    return (
        "<b>👤 Your Profile</b>\n\n"
        f"<b>Name:</b> {full_name}{username_line}\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Gender:</b> {'Male' if user.get('gender') == 'M' else 'Female'}\n"
        f"<b>Age:</b> {user.get('age')}\n"
        f"<b>Country:</b> {esc(str(user.get('country')))}\n"
        f"<b>Interests:</b> {prefs_text}\n"
        f"<b>Rating:</b> {up_votes} 👍 {down_votes} 👎\n"
        f"<b>Points:</b> {user.get('points', 0)}\n"
        f"{streak_line}\n"
        f"{filter_line}"
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
    if user_id not in init.user_details:
        await init.ensure_user_loaded(user_id)
    text = await _build_profile_text(user_id, context)
    if not text:
        return
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=text, reply_markup=_profile_keyboard(), parse_mode="HTML")


async def handle_profile_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns to profile view when Back to Profile is pressed."""
    query = update.callback_query
    if not query:
        return
    await query.answer()
    user_id = update.effective_user.id
    text = await _build_profile_text(
        user_id, context,
        fallback_name=update.effective_user.full_name,
        fallback_username=update.effective_user.username,
    )
    if text:
        await safe_tele_func_call(
            query.edit_message_text,
            text=text,
            reply_markup=_profile_keyboard(),
            parse_mode="HTML"
        )
