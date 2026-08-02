# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from handlers.rating import ask_for_rating  # Imports the handler which asks for the user to rate their partner after a conversation
from security import safe_tele_func_call
from games.registry import end_any_active_game
from games.game_requests import clear_pending_requests
from message import PARTNER_LEFT_CHAT_TEXT, CHAT_ENDED_TEXT, REMOVED_FROM_QUEUE_TEXT, NOT_IN_CHAT_TEXT

import init  # Importing the bot credentials and users' details


# Stops the conversation between the user and their partner
@check_user_profile
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:  # Checks if the user is in a active conversation
        partner = init.active_pairs.pop(user_id)
        init.user_details[partner]["partner_id"] = None
        init.user_details[user_id]["partner_id"] = None
        init.active_pairs.pop(partner, None)
        init.message_map.pop(user_id, None)  # Clears the reply/reaction relay mapping for the ended pair
        init.message_map.pop(partner, None)

        init.dirty_users.update([user_id, partner])

        # End any mini-game in progress so nobody's left hanging
        await end_any_active_game(context, user_id)
        await end_any_active_game(context, partner)

        # Clear any pending game requests too, otherwise one could be accepted later
        # against a partner who's no longer around
        clear_pending_requests(user_id)
        clear_pending_requests(partner)

        # Notifies the user and their partner that the conversation is ended
        await safe_tele_func_call(context.bot.send_message, chat_id=partner, text=PARTNER_LEFT_CHAT_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=CHAT_ENDED_TEXT, parse_mode="HTML")

        # Asks both the users to rate each other
        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)
    elif user_id in init.waiting_users:  # If the user is waiting they are popped out of the waiting_users list
        init.waiting_users.remove(user_id)
        init.wait_started.pop(user_id, None)
        await safe_tele_func_call(update.message.reply_text, text=REMOVED_FROM_QUEUE_TEXT, parse_mode="HTML")
    else:  # Notifies that the user is neither in an active conversation nor in waiting_users list
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
