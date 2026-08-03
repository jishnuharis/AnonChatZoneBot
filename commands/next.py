# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from commands.find import find  # Imports the command functionality which finds partner for a user

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from handlers.rating import ask_for_rating  # Imports the handler which asks for the user to rate their partner after a conversation
from security import safe_tele_func_call
from games.registry import end_any_active_game
from games.game_requests import clear_pending_requests
from message import PARTNER_LEFT_CHAT_TEXT, PARTNER_SKIPPED_TEXT, NOT_IN_CHAT_USE_FIND_TEXT

import init  # Importing the bot credentials and users' details


# Function skips the current partner and goes on to find the next partner
@check_user_profile
async def skip_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Daily credit cap - free users get FREE_DAILY_CREDIT_LIMIT credits/day shared
    # between /next skips and media sends (see relay.py), subscribers get more
    # depending on their tier. Checked before anything else changes state, so a
    # capped-out user just gets told "no" and stays with their current partner
    # rather than getting yanked out of their chat.
    if user_id in init.active_pairs:  # Checks if the user is in an active conversation with their partner
        partner = init.active_pairs.pop(user_id)
        init.user_details[partner]["partner_id"] = None
        init.user_details[user_id]["partner_id"] = None
        init.active_pairs.pop(partner, None)  # Pops the partner's ID from the active_pair
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

        # Notify the user and his partner that the conversation is ended
        await safe_tele_func_call(context.bot.send_message, chat_id=partner, text=PARTNER_LEFT_CHAT_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=PARTNER_SKIPPED_TEXT, parse_mode="HTML")

        # Ask both users to rate each other
        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)

        await find(update, context)  # Finds a new partner for the user
    else:  # Notifies the user that they are not in an active conversation
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_USE_FIND_TEXT, parse_mode="HTML")
