from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import HELP_TEXT


@check_user_profile
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_tele_func_call(update.message.reply_text, text=HELP_TEXT, parse_mode="HTML")
