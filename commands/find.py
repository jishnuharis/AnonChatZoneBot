# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Function which pushes the user's ID into waiting_users list to find a partner later on
@check_user_profile
async def find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.active_pairs:  # Checks if the user is already in a chat and notifies if they are in a chat already
        await safe_tele_func_call(update.message.reply_text, text="⚠️ *You're already in a chat.*\nUse /stop or /next first.", parse_mode="Markdown")
        return
    if user_id not in init.waiting_users:  # Pushes the user's ID into the waiting_users list if it's not already in the list
        init.waiting_users.append(user_id)
        await safe_tele_func_call(update.message.reply_text, text="🔍*Looking for a partner...*", parse_mode="Markdown")  # Notifies the user
    if len(init.waiting_users) >= 2:  # If there are more than 2 users waiting, pairs them up and pops them from the waiting_users list
        user1 = init.waiting_users.pop(0)
        user2 = init.waiting_users.pop(0)
        init.active_pairs[user1] = user2
        init.active_pairs[user2] = user1
        uv1, uv2 = init.user_details[user1]["votes"], init.user_details[user2]["votes"]
        init.user_details[user1]["partner_id"] = user2
        init.user_details[user2]["partner_id"] = user1
        await safe_tele_func_call(context.bot.send_message, chat_id=user1, text=f"🎯 *Found Someone.... Say Hi!!*\nRating: {uv2['up']} 👍 {uv2['down']} 👎\n/next - Next Chat\n/stop - Stop Chat", parse_mode="Markdown")
        await safe_tele_func_call(context.bot.send_message, chat_id=user2, text=f"🎯 *Found Someone.... Say Hi!!*\nRating: {uv1['up']} 👍 {uv1['down']} 👎\n/next - Next Chat\n/stop - Stop Chat", parse_mode="Markdown")

        init.dirty_users.update([user1, user2])
