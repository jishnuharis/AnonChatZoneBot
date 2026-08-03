from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.country import send_country_selection
from handlers.preferences import send_preferences_menu
from security import safe_tele_func_call
from message import SELECT_NEW_GENDER_TEXT, ENTER_NEW_AGE_TEXT

import init


async def handle_edit_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data.split("|")[1]

    if action == "gender":
        keyboard = [[InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                     InlineKeyboardButton("♀️ Female", callback_data="gender|F")]]
        await safe_tele_func_call(query.edit_message_text, text=SELECT_NEW_GENDER_TEXT, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        init.edit_stage[user_id] = "gender"
    elif action == "age":
        await safe_tele_func_call(query.edit_message_text, text=ENTER_NEW_AGE_TEXT, parse_mode="HTML")
        init.edit_stage[user_id] = "age"
    elif action == "country":
        await safe_tele_func_call(context.bot.delete_message, chat_id=query.message.chat.id, message_id=query.message.message_id)
        init.edit_stage[user_id] = "country"
        await send_country_selection(user_id, context)
    elif action == "preferences":
        await safe_tele_func_call(context.bot.delete_message, chat_id=query.message.chat.id, message_id=query.message.message_id)
        init.edit_stage[user_id] = "preferences"
        await send_preferences_menu(user_id, context, first_time=False)

    init.dirty_users.add(user_id)
