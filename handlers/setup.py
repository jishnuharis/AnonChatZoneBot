# Imports everything needed from the telegram module
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from functools import wraps

from handlers.country import send_country_selection  # Imports the Handler which sends the country selection menu to the user
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Checks if the user profile exists
def check_user_profile(handler_func):
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in init.user_details:  # If the user's ID is not in the users' database and if it's not present then it initialises the row
            init.user_details[user_id] = {
                "gender": None,
                "age": None,
                "country": None,
                "reports": 0,
                "reporters": [],
                "votes": {"up": 0, "down": 0},
                "voters": [],
                "feedback_track": {}
            }
            init.user_input_stage[user_id] = "gender"  # Sets the input stage of the user to gender
            keyboard = [[
                InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                InlineKeyboardButton("♀️ Female", callback_data="gender|F")
            ]]
            markup = InlineKeyboardMarkup(keyboard)
            await safe_tele_func_call(update.message.reply_text, text="👋 Welcome to *Chat Zone - Anonymous Chat Bot!*", parse_mode="Markdown")
            await safe_tele_func_call(update.message.reply_text, text="*Let's set up your profile.*\nWhat's your gender?", reply_markup=markup, parse_mode="Markdown")
            return

        if not all([init.user_details[user_id].get("gender"), init.user_details[user_id].get("age"), init.user_details[user_id].get("country")]):  # Checks if every user detail is saved or not
            stage = init.user_input_stage.get(user_id, "gender")  # if not first sets the input stage to gender
            if stage == "gender":  # If stage is in gender it shows the menu to ask the user for selection
                keyboard = [[
                    InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                    InlineKeyboardButton("♀️ Female", callback_data="gender|F")
                ]]
                markup = InlineKeyboardMarkup(keyboard)
                await safe_tele_func_call(update.message.reply_text, text="*Please select your gender: *", reply_markup=markup, parse_mode="Markdown")
            elif stage == "age":  # If the stage is in age then it asks the user to enter the age
                await safe_tele_func_call(update.message.reply_text, text="📅 *Please enter your age:*", parse_mode="Markdown")
            return

        init.dirty_users.add(user_id)

        return await handler_func(update, context)
    return wrapper


# Handles the user profile setup
async def handle_user_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if user_id in init.edit_stage and init.edit_stage[user_id] == "age":  # checks if the user is in editing stage and wants to edit their age
        try:  # Tries to get the input in integer format and puts it in the user's details row
            age = int(text)
            init.user_details[user_id]["age"] = age
            del init.edit_stage[user_id]
            await safe_tele_func_call(update.message.reply_text, text=f"✅ *Age updated to {age}.*", parse_mode="Markdown")
        except ValueError:  # If the user inputs something else it will notify them to do it again
            await safe_tele_func_call(update.message.reply_text, text="❌ *Please enter a valid number for age.*", parse_mode="Markdown")
        return

    # This part works if the user is setting up their profile for the first time
    if user_id not in init.user_input_stage:
        return

    stage = init.user_input_stage[user_id]
    if stage == "age":  # Checks if the user is in the age input stage and asks the user to enter their age
        try:  # Tries to get the input in integer format and puts it in the user's details row
            age = int(text)
            init.user_details[user_id]["age"] = age
            init.user_input_stage[user_id] = "country"
            await safe_tele_func_call(update.message.reply_text, text=f"✅ *Age set to {age}.*\n🌍 Great! Now, please select your country:", parse_mode="Markdown")
            await send_country_selection(user_id, context)
        except ValueError:  # If the user inputs something else it will notify them to do it again
            await safe_tele_func_call(update.message.reply_text, text="❌ *Please enter a valid number for age.*", parse_mode="Markdown")

    init.dirty_users.add(user_id)
