from typing import Tuple
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.country import send_country_selection
from handlers.preferences import send_preferences_menu
from security import safe_tele_func_call
from message import SELECT_NEW_GENDER_TEXT, ENTER_NEW_AGE_TEXT
import subscription

import init


def build_match_filters_keyboard(user_id: int) -> Tuple[str, InlineKeyboardMarkup]:
    details = init.user_details.setdefault(user_id, init._default_user())
    pref_g = details.get("pref_gender", "ANY")
    pref_c = details.get("pref_country", "ANY")

    gender_labels = {"ANY": "🌐 Any Gender", "F": "♀️ Female Only", "M": "♂️ Male Only"}
    country_labels = {"ANY": "🌐 Any Country", "SAME": f"📍 Same Country ({details.get('country', 'Mine')})"}

    g_text = gender_labels.get(pref_g, "🌐 Any Gender")
    c_text = country_labels.get(pref_c, f"📍 {pref_c}")

    text = (
        "⭐ <b>Matchmaking Preferences (Subscriber Perk)</b>\n\n"
        "Configure who you get paired with when using /find:\n\n"
        f"• <b>Preferred Gender:</b> <code>{g_text}</code>\n"
        f"• <b>Preferred Country:</b> <code>{c_text}</code>\n\n"
        "<i>Tap a filter below to toggle your preferred partner settings:</i>"
    )

    keyboard = [
        [InlineKeyboardButton(f"Gender: {g_text}", callback_data="edit|pref_gender")],
        [InlineKeyboardButton(f"Country: {c_text}", callback_data="edit|pref_country")],
        [InlineKeyboardButton("« Back to Profile", callback_data="edit|back_to_profile")]
    ]
    return text, InlineKeyboardMarkup(keyboard)


async def handle_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts = query.data.split("|")
    action = parts[1]

    if action == "gender":
        keyboard = [[InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                     InlineKeyboardButton("♀️ Female", callback_data="gender|F")]]
        await safe_tele_func_call(query.edit_message_text, text=SELECT_NEW_GENDER_TEXT, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        init.edit_stage[user_id] = "gender"
    elif action == "age":
        await safe_tele_func_call(query.edit_message_text, text=ENTER_NEW_AGE_TEXT, parse_mode="HTML")
        init.edit_stage[user_id] = "age"
    elif action == "country":
        await safe_tele_func_call(context.bot.delete_message, chat_id=query.message.chat.id, message_id=query.message.message_id)
        init.edit_stage[user_id] = "country"
        await send_country_selection(user_id, context)
    elif action == "preferences":
        await safe_tele_func_call(context.bot.delete_message, chat_id=query.message.chat.id, message_id=query.message.message_id)
        init.edit_stage[user_id] = "preferences"
        await send_preferences_menu(user_id, context, first_time=False)
    elif action == "match_filters":
        if not subscription.is_subscribed(user_id):
            keyboard = [
                [InlineKeyboardButton("⭐ View Subscription Plans", callback_data="sub|upgrade_prompt")],
                [InlineKeyboardButton("« Back to Profile", callback_data="edit|back_to_profile")]
            ]
            text = (
                "⭐ <b>Subscriber Perk: Match Filters</b>\n\n"
                "Filter your chat partners by <b>Gender</b> and <b>Country</b>!\n\n"
                "• <i>Match only with Females or Males</i>\n"
                "• <i>Match only with users from the Same Country or Any Country</i>\n\n"
                "Subscribe with Telegram Stars via /subscribe to unlock custom filters!"
            )
            await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            return
        text, markup = build_match_filters_keyboard(user_id)
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=markup, parse_mode="HTML")
    elif action == "pref_gender":
        if not subscription.is_subscribed(user_id):
            return
        keyboard = [
            [InlineKeyboardButton("🌐 Any Gender", callback_data="edit|set_pref_g|ANY")],
            [InlineKeyboardButton("♀️ Female Only", callback_data="edit|set_pref_g|F")],
            [InlineKeyboardButton("♂️ Male Only", callback_data="edit|set_pref_g|M")],
            [InlineKeyboardButton("« Back", callback_data="edit|match_filters")]
        ]
        text = "⭐ <b>Select Preferred Partner Gender:</b>"
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif action == "set_pref_g":
        if not subscription.is_subscribed(user_id):
            return
        val = parts[2]
        init.user_details.setdefault(user_id, init._default_user())["pref_gender"] = val
        init.dirty_users.add(user_id)
        text, markup = build_match_filters_keyboard(user_id)
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=markup, parse_mode="HTML")
    elif action == "pref_country":
        if not subscription.is_subscribed(user_id):
            return
        u_country = init.user_details.get(user_id, {}).get("country", "Unknown")
        keyboard = [
            [InlineKeyboardButton("🌐 Any Country", callback_data="edit|set_pref_c|ANY")],
            [InlineKeyboardButton(f"📍 Same Country ({u_country})", callback_data="edit|set_pref_c|SAME")],
            [InlineKeyboardButton("« Back", callback_data="edit|match_filters")]
        ]
        text = "⭐ <b>Select Preferred Partner Country:</b>"
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    elif action == "set_pref_c":
        if not subscription.is_subscribed(user_id):
            return
        val = parts[2]
        init.user_details.setdefault(user_id, init._default_user())["pref_country"] = val
        init.dirty_users.add(user_id)
        text, markup = build_match_filters_keyboard(user_id)
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=markup, parse_mode="HTML")
    elif action == "back_to_profile":
        from commands.profile import _build_profile_text, _profile_keyboard
        text = await _build_profile_text(user_id, context)
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=_profile_keyboard(), parse_mode="HTML")

    init.dirty_users.add(user_id)
