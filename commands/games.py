from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from games.game_requests import GAME_MODULES
from message import NEED_PARTNER_FOR_GAME_TEXT, PICK_GAME_TEXT, SENDING_GAME_REQUEST_TEXT

import init


@check_user_profile
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not init.user_details.get(user_id, {}).get("partner_id"):
        await safe_tele_func_call(update.message.reply_text, text=NEED_PARTNER_FOR_GAME_TEXT, parse_mode="HTML")
        return

    keyboard = [[InlineKeyboardButton(label, callback_data=f"gamemenu|{game_type}")] for game_type, (label, _module) in GAME_MODULES.items()]
    await safe_tele_func_call(update.message.reply_text, text=PICK_GAME_TEXT, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def handle_games_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from games.game_requests import send_request

    query = update.callback_query
    await query.answer()
    game_type = query.data.split("|")[1]
    await safe_tele_func_call(query.edit_message_text, text=SENDING_GAME_REQUEST_TEXT, parse_mode="HTML")
    await send_request(update, context, game_type)
