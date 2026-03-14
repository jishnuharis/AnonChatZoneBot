# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Handles the gender selection from the user
async def handle_gender_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Gets the query from the user
    user_id = query.from_user.id
    gender = query.data.split("|")[1]

    if user_id in init.edit_stage and init.edit_stage[user_id] == "gender":  # Checks if the user is in editing stage and wants to edit their gender
        init.user_details[user_id]["gender"] = gender
        del init.edit_stage[user_id]
        await safe_tele_func_call(query.edit_message_text, text=f"*Gender updated to {'Male' if gender=='M' else 'Female'}.*", parse_mode="Markdown")  # Notifies the user that their gender is updated
        return

    # This part works if the user is setting up their profile for the first time
    init.user_details[user_id]["gender"] = gender
    init.user_input_stage[user_id] = "age"
    await safe_tele_func_call(query.edit_message_text, text=f"*Gender is set to {'Male' if gender == 'M' else 'Female'}.*\n📅 Please enter your age:", parse_mode="Markdown")

    init.dirty_users.add(user_id)
