# Imports everything needed from the telegram module
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.country import send_country_selection  # Imports the Handler which sends the country selection menu to the user
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Handles the selection of the user to edit their details
async def handle_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data.split("|")[1]

    if action == "gender":  # Checks if the user wants to edit their gender and shows a menu for it
        keyboard = [[InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                     InlineKeyboardButton("♀️ Female", callback_data="gender|F")]]
        await safe_tele_func_call(query.edit_message_text, text="*Select your new gender:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        init.edit_stage[user_id] = "gender"
    elif action == "age":  # Checks if the user wants to edit their age and asks them to enter their age
        await safe_tele_func_call(query.edit_message_text, text="📅 *Please enter your new age:*", parse_mode="Markdown")
        init.edit_stage[user_id] = "age"
    elif action == "country":  # Checks if the user wants to edit the country and sends a selection menu for them to select
        await safe_tele_func_call(query.edit_message_text, text="🌍 *Select your new country:*", parse_mode="Markdown")
        init.edit_stage[user_id] = "country"
        await send_country_selection(user_id, context)

    init.dirty_users.add(user_id)
