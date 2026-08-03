from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from handlers.preferences import send_preferences_menu
from message import SELECT_COUNTRY_TEXT

import init
import referral


async def send_country_selection(user_id, context):
    countries = [
        ("🇮🇳 India", "India"), ("🇺🇸 USA", "USA"),
        ("🇬🇧 UK", "UK"), ("🇨🇦 Canada", "Canada"),
        ("🇦🇺 Australia", "Australia"), ("🇫🇷 France", "France"),
        ("🇩🇪 Germany", "Germany"), ("🇮🇩 Indonesia", "Indonesia"),
        ("🇷🇺 Russia", "Russia"), ("🇧🇷 Brazil", "Brazil")
    ]
    keyboard = []
    for i in range(0, len(countries), 2):
        row = [
            InlineKeyboardButton(countries[i][0], callback_data=f"country|{countries[i][1]}"),
            InlineKeyboardButton(countries[i + 1][0], callback_data=f"country|{countries[i + 1][1]}")
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🌐 Other", callback_data="country|Other")])
    markup = InlineKeyboardMarkup(keyboard)
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=SELECT_COUNTRY_TEXT, reply_markup=markup, parse_mode="HTML")


async def handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    country = query.data.split("|")[1]

    if user_id in init.edit_stage and init.edit_stage[user_id] == "country":
        init.user_details[user_id]["country"] = country
        del init.edit_stage[user_id]
        init.dirty_users.add(user_id)
        await safe_tele_func_call(query.edit_message_text, text=f"✅ <i>Country updated to</i> <b>{country}</b>.", parse_mode="HTML")

        from commands.profile import send_profile_menu
        await send_profile_menu(context, user_id)
        return

    init.user_details[user_id]["country"] = country
    await safe_tele_func_call(query.edit_message_text, text=f"✅ <i>Country set to</i> <b>{country}</b>.", parse_mode="HTML")

    await referral.credit_referral(context, user_id)

    init.user_input_stage[user_id] = "preferences"
    await send_preferences_menu(user_id, context, first_time=True)

    init.dirty_users.add(user_id)
