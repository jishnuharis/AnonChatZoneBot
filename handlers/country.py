# Imports everything needed from the telegram module
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Function sends a selection menu of every country loaded into it in the form of buttons
async def send_country_selection(user_id, context):
    countries = [
        ("🇮🇳 India", "India"), ("🇺🇸 USA", "USA"),
        ("🇬🇧 UK", "UK"), ("🇨🇦 Canada", "Canada"),
        ("🇦🇺 Australia", "Australia"), ("🇫🇷 France", "France"),
        ("🇩🇪 Germany", "Germany"), ("🇮🇩 Indonesia", "Indonesia"),
        ("🇷🇺 Russia", "Russia"), ("🇧🇷 Brazil", "Brazil")
    ]  # Holds every country and its emojis as elements of the list
    keyboard = []  # Initialises the keyboard
    for i in range(0, len(countries), 2):  # Splits the countries and their button to only be two in a row
        row = [
            InlineKeyboardButton(countries[i][0], callback_data=f"country|{countries[i][1]}"),
            InlineKeyboardButton(countries[i + 1][0], callback_data=f"country|{countries[i + 1][1]}")
        ]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🌐 Other", callback_data="country|Other")])
    markup = InlineKeyboardMarkup(keyboard)
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text="🌍 *Select your country:*", reply_markup=markup, parse_mode="Markdown")  # Shows the buttons to the user to select


# Function handles the selection done by the user to select the country
async def handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Gets the query from the user input
    user_id = query.from_user.id
    country = query.data.split("|")[1]

    if user_id in init.edit_stage and init.edit_stage[user_id] == "country":  # Checks if the user is in editing stage and wants to edit the country
        init.user_details[user_id]["country"] = country
        del init.edit_stage[user_id]
        await safe_tele_func_call(query.edit_message_text, text=f"✅ *Country updated to {country}.*", parse_mode="Markdown")  # Notifies that the country is updated
        return

    # This part works if the user is setting up their profile for the first time
    init.user_details[user_id]["country"] = country
    del init.user_input_stage[user_id]
    await safe_tele_func_call(query.edit_message_text, text=f"✅ *Country set to {country}.*\nYou're all set! Use /find to start chatting.", parse_mode="Markdown")

    init.dirty_users.add(user_id)
