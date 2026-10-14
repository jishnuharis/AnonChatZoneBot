import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import HELP_TEXT, HELP_GROUP_REDIRECT_TEXT
from commands.subscribe import get_admin_contact_url
import init


@check_user_profile
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from group_helper import is_group_chat, get_group_redirect_keyboard
    bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
    admin_url = get_admin_contact_url()
    formatted_help = HELP_TEXT.format(admin_url=admin_url)

    if is_group_chat(update):
        text = f"{formatted_help}\n\n{HELP_GROUP_REDIRECT_TEXT}"
        keyboard = get_group_redirect_keyboard(bot_username, "help")
        await safe_tele_func_call(
            update.message.reply_text,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👑 Upgrade to VIP", callback_data="sub|upgrade_prompt"),
            InlineKeyboardButton("💬 Community Group", url=init.GROUP_URL),
        ]
    ])
    await safe_tele_func_call(
        update.message.reply_text,
        text=formatted_help,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
