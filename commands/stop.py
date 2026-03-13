# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from handlers.rating import ask_for_rating  # Imports the handler which asks for the user to rate their partner after a conversation
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Stops the conversation between the user and their partner
@check_user_profile
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:  # Checks if the user is in a active conversation
        partner = init.active_pairs.pop(user_id)
        init.user_details[partner]["partner_id"] = -1
        init.user_details[user_id]["partner_id"] = -1
        init.active_pairs.pop(partner, None)

        # Notifies the user and their partner thar the conversation is ended
        await safe_tele_func_call(context.bot.send_message, chat_id=partner, text="⛔ *Your partner left the chat.*", parse_mode="Markdown")
        await safe_tele_func_call(update.message.reply_text, text="👋 *Chat ended.*", parse_mode="Markdown")

        # Asks both the users to rate each other
        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)
    elif user_id in init.waiting_users:  # If the user is waiting they are popped out of the waiting_users list
        init.waiting_users.remove(user_id)
        await safe_tele_func_call(update.message.reply_text, text="❗ *You've been popped out of the Waiting Queue.*\nUse /find to search for a partner.", parse_mode="Markdown")
    else:  # Notifies that the user is neither in an active conversation nor in waiting_users list
        await safe_tele_func_call(update.message.reply_text, text="❗*You're not in a chat.*", parse_mode="Markdown")
