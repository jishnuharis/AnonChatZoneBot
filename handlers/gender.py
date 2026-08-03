from telegram import Update
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import init


async def handle_gender_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    gender = query.data.split("|")[1]

    if user_id in init.edit_stage and init.edit_stage[user_id] == "gender":
        init.user_details[user_id]["gender"] = gender
        del init.edit_stage[user_id]
        await safe_tele_func_call(query.edit_message_text, text=f"✅ <i>Gender updated to</i> <b>{'Male' if gender == 'M' else 'Female'}</b>.", parse_mode="HTML")
        init.dirty_users.add(user_id)

        from commands.profile import send_profile_menu
        await send_profile_menu(context, user_id)
        return

    init.user_details[user_id]["gender"] = gender
    init.user_input_stage[user_id] = "age"
    await safe_tele_func_call(query.edit_message_text, text=f"<i>Gender set to</i> <b>{'Male' if gender == 'M' else 'Female'}</b>.\n📅 <b>Please enter your age:</b>", parse_mode="HTML")

    init.dirty_users.add(user_id)
