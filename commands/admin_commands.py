from telegram import Update
from telegram.ext import ContextTypes
import asyncio

from security import safe_tele_func_call

import init


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != init.OWNER:
        await update.message.reply_text("You can't use this command 💀")
        return

    message = " ".join(context.args)
    if not message:
        await update.message.reply_text("Give me a message to broadcast!")
        return

    sent = 0
    for user_id in init.user_details.keys():
        try:
            await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=message)
            sent += 1
            await asyncio.sleep(0.1)  # tiny delay to avoid hitting rate limits
        except Exception as e:
            await update.message.reply_text(f"An Unexpected error occurred: {e}")

    await update.message.reply_text(f"Broadcast sent to {sent} users ✅")
