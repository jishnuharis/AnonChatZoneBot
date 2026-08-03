from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from message import (
    PREFERENCES_INTRO_FIRST_TIME_TEXT, PREFERENCES_INTRO_UPDATE_TEXT,
    DONE_BUTTON_LABEL, DONE_SKIP_BUTTON_LABEL, NONE_PICKED_YET_TEXT,
)

import init


def build_preferences_keyboard(bitmask: int, done_label=DONE_BUTTON_LABEL) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for i, (label, emoji) in enumerate(init.PREFERENCE_TAGS):
        checked = "✅" if bitmask & (1 << i) else "⬜"
        row.append(InlineKeyboardButton(f"{checked} {emoji} {label}", callback_data=f"pref|toggle|{i}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(done_label, callback_data="pref|done")])
    return InlineKeyboardMarkup(rows)


def describe_preferences(bitmask: int) -> str:
    tags = [f"{emoji} {label}" for i, (label, emoji) in enumerate(init.PREFERENCE_TAGS) if bitmask & (1 << i)]
    return ", ".join(tags) if tags else NONE_PICKED_YET_TEXT


async def send_preferences_menu(chat_id, context: ContextTypes.DEFAULT_TYPE, first_time=False):
    bitmask = init.user_details.get(chat_id, {}).get("preferences", 0)
    intro = PREFERENCES_INTRO_FIRST_TIME_TEXT if first_time else PREFERENCES_INTRO_UPDATE_TEXT
    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=chat_id,
        text=intro,
        reply_markup=build_preferences_keyboard(bitmask, DONE_BUTTON_LABEL if not first_time else DONE_SKIP_BUTTON_LABEL),
        parse_mode="HTML",
    )


async def handle_preferences_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action = query.data.split("|")[1]

    details = init.user_details.setdefault(user_id, {})
    bitmask = details.get("preferences", 0)

    if action == "toggle":
        bit = int(query.data.split("|")[2])
        bitmask ^= (1 << bit)
        details["preferences"] = bitmask
        init.dirty_users.add(user_id)
        await safe_tele_func_call(query.edit_message_reply_markup, reply_markup=build_preferences_keyboard(bitmask))
        return

    if action == "done":
        finishing_setup = user_id in init.user_input_stage
        if user_id in init.user_input_stage:
            del init.user_input_stage[user_id]
        if user_id in init.edit_stage:
            del init.edit_stage[user_id]

        if finishing_setup:
            text = (
                f"✅ <i>Interests saved:</i> {describe_preferences(bitmask)}\n\n"
                f"<b>You're all set! Use</b> /find <b>to start chatting.</b>"
            )
            await safe_tele_func_call(query.edit_message_text, text=text, parse_mode="HTML")
        else:
            text = f"✅ <i>Interests updated:</i> {describe_preferences(bitmask)}"
            await safe_tele_func_call(query.edit_message_text, text=text, parse_mode="HTML")

            from commands.profile import send_profile_menu  # Lazy import to dodge a circular import
            await send_profile_menu(context, user_id)

        init.dirty_users.add(user_id)
