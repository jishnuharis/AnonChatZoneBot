# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call
from message import WELCOME_BACK_TEXT

import init  # Importing the bot credentials and users' details


# Starts the bot for the user and goes on to ask for the user details if they are new or else welcomes them
@check_user_profile
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not all([init.user_details[user_id].get("gender"), init.user_details[user_id].get("age"), init.user_details[user_id].get("country")]):
        return
    await safe_tele_func_call(update.message.reply_text, text=WELCOME_BACK_TEXT, parse_mode="HTML")
