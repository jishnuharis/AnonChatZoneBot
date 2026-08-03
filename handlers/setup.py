from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from functools import wraps

from handlers.country import send_country_selection
from security import safe_tele_func_call
from message import (
    WELCOME_NEW_USER_TEXT, SETUP_PROFILE_GENDER_PROMPT_TEXT, SELECT_GENDER_TEXT,
    ENTER_AGE_TEXT, INVALID_AGE_TEXT, PREFERENCES_BUTTONS_NUDGE_TEXT,
)

import init
import referral


def check_user_profile(handler_func):
    @wraps(handler_func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id

        if user_id not in init.user_details:
            init.user_details[user_id] = init._default_user()
            referral.capture_referral(context, user_id)
            init.user_input_stage[user_id] = "gender"
            keyboard = [[
                InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                InlineKeyboardButton("♀️ Female", callback_data="gender|F")
            ]]
            markup = InlineKeyboardMarkup(keyboard)
            await safe_tele_func_call(update.message.reply_text, text=WELCOME_NEW_USER_TEXT, parse_mode="HTML")
            await safe_tele_func_call(update.message.reply_text, text=SETUP_PROFILE_GENDER_PROMPT_TEXT, reply_markup=markup, parse_mode="HTML")
            return

        if not all([init.user_details[user_id].get("gender"), init.user_details[user_id].get("age"), init.user_details[user_id].get("country")]):
            stage = init.user_input_stage.get(user_id, "gender")
            if stage == "gender":
                keyboard = [[
                    InlineKeyboardButton("♂️ Male", callback_data="gender|M"),
                    InlineKeyboardButton("♀️ Female", callback_data="gender|F")
                ]]
                markup = InlineKeyboardMarkup(keyboard)
                await safe_tele_func_call(update.message.reply_text, text=SELECT_GENDER_TEXT, reply_markup=markup, parse_mode="HTML")
            elif stage == "age":
                await safe_tele_func_call(update.message.reply_text, text=ENTER_AGE_TEXT, parse_mode="HTML")
            return

        init.dirty_users.add(user_id)

        return await handler_func(update, context)
    return wrapper


async def handle_user_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip() if update.message.text else ""

    if user_id in init.edit_stage and init.edit_stage[user_id] == "age":
        try:
            age = int(text)
            if not (13 <= age <= 100):
                raise ValueError
            init.user_details[user_id]["age"] = age
            del init.edit_stage[user_id]
            await safe_tele_func_call(update.message.reply_text, text=f"✅ <i>Age updated to</i> <b>{age}</b>.", parse_mode="HTML")
            init.dirty_users.add(user_id)

            from commands.profile import send_profile_menu
            await send_profile_menu(context, user_id)
        except ValueError:
            await safe_tele_func_call(update.message.reply_text, text=INVALID_AGE_TEXT, parse_mode="HTML")
        return

    if user_id not in init.user_input_stage:
        return

    stage = init.user_input_stage[user_id]
    if stage == "age":
        try:
            age = int(text)
            if not (13 <= age <= 100):
                raise ValueError
            init.user_details[user_id]["age"] = age
            init.user_input_stage[user_id] = "country"
            await safe_tele_func_call(update.message.reply_text, text=f"✅ <i>Age set to</i> <b>{age}</b>.\n🌍 <b>Great! Now, please select your country:</b>", parse_mode="HTML")
            await send_country_selection(user_id, context)
        except ValueError:
            await safe_tele_func_call(update.message.reply_text, text=INVALID_AGE_TEXT, parse_mode="HTML")
    elif stage == "preferences":
        await safe_tele_func_call(update.message.reply_text, text=PREFERENCES_BUTTONS_NUDGE_TEXT, parse_mode="HTML")

    init.dirty_users.add(user_id)
