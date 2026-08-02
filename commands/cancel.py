# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call
from games.registry import get_active, end_any_active_game
from message import (
    GAME_CANCELLED_TEXT, GAME_REQUEST_CANCELLED_TEXT, PARTNER_CANCELLED_REQUEST_TEXT,
    NOTHING_TO_CANCEL_TEXT,
)

import init  # Importing the bot credentials and users' details


# Lets a user back out of a mini-game (or a still-pending game request) on their own,
# without having to end the whole anonymous chat with /stop. Checks, in order:
#   1. an active game -> force-ends it (same mechanics as /stop's game cleanup)
#   2. an incoming request waiting on this user to accept/decline -> declines it
#   3. an outgoing request this user sent that's still waiting on their partner -> withdraws it
@check_user_profile
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 1) Currently playing a mini-game -> end it for both players, chat stays open
    if get_active(user_id):
        await end_any_active_game(context, user_id)
        await safe_tele_func_call(update.message.reply_text, text=GAME_CANCELLED_TEXT, parse_mode="HTML")
        return

    # 2) An incoming game request is waiting on this user -> decline it
    incoming = init.game_requests.get(user_id)
    if incoming:
        requester_id = incoming["from"]
        init.game_requests.pop(user_id, None)
        await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
        return

    # 3) This user sent a request that's still waiting on their partner -> withdraw it
    for target_id, req in list(init.game_requests.items()):
        if req["from"] == user_id:
            init.game_requests.pop(target_id, None)
            await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
            await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
            return

    # Nothing to cancel
    await safe_tele_func_call(update.message.reply_text, text=NOTHING_TO_CANCEL_TEXT, parse_mode="HTML")
