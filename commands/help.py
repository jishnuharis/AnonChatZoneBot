from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import HELP_TEXT
import init


@check_user_profile
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Community Group", url=init.GROUP_URL),
        ]
    ])
    await safe_tele_func_call(
        update.message.reply_text,
        text=HELP_TEXT,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
