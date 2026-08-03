from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from games.registry import get_active, end_any_active_game
from message import (
    GAME_CANCELLED_TEXT, GAME_REQUEST_CANCELLED_TEXT, PARTNER_CANCELLED_REQUEST_TEXT,
    NOTHING_TO_CANCEL_TEXT,
)

import init


@check_user_profile
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if get_active(user_id):
        await end_any_active_game(context, user_id)
        await safe_tele_func_call(update.message.reply_text, text=GAME_CANCELLED_TEXT, parse_mode="HTML")
        return

    incoming = init.game_requests.get(user_id)
    if incoming:
        requester_id = incoming["from"]
        init.game_requests.pop(user_id, None)
        await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
        return

    for target_id, req in list(init.game_requests.items()):
        if req["from"] == user_id:
            init.game_requests.pop(target_id, None)
            await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
            await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
            return

    await safe_tele_func_call(update.message.reply_text, text=NOTHING_TO_CANCEL_TEXT, parse_mode="HTML")
