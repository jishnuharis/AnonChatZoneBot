# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import WELCOME_BACK_TEXT

import init


@check_user_profile
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not all([init.user_details[user_id].get("gender"), init.user_details[user_id].get("age"), init.user_details[user_id].get("country")]):
        return
    await safe_tele_func_call(update.message.reply_text, text=WELCOME_BACK_TEXT, parse_mode="HTML")
