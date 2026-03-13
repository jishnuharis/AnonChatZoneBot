# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from commands.find import find  # Imports the command functionality which finds partner for a user

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from handlers.rating import ask_for_rating  # Imports the handler which asks for the user to rate their partner after a conversation
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Function skips the current partner and goes on to find the next partner
@check_user_profile
async def next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:  # Checks if the user is in an active conversation with their partner
        partner = init.active_pairs.pop(user_id)
        init.user_details[partner]["partner_id"] = -1
        init.user_details[user_id]["partner_id"] = -1
        init.active_pairs.pop(partner, None)  # Pops the partner's ID from the active_pair

        # Notify the user and his partner that the conversation us ended
        await safe_tele_func_call(context.bot.send_message, chat_id=partner, text="⛔ *Your partner left the chat.*", parse_mode="Markdown")
        await safe_tele_func_call(update.message.reply_text, text="🔁 *Partner skipped...\nYou're added to the waiting queue...\nFinding new one...*", parse_mode="Markdown")

        # Ask both users to rate each other
        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)

        await find(update, context)  # Finds a new partner for the user
    else:  # Notifies the user that they are not in an active conversation
        await safe_tele_func_call(update.message.reply_text, text="❗*You're not in a chat.*\nUse /find to connect.", parse_mode="Markdown")
