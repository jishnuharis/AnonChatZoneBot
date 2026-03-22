from telegram import Update
from telegram.ext import ContextTypes
import asyncio

from security import safe_tele_func_call

import init


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(init.OWNER):
        await update.message.reply_text("You can't use this command 💀")
        return

    # get the full message text including line breaks
    message = update.message.text
    if message.lower().startswith("/broadcast"):
        message = message[len("/broadcast"):].lstrip()  # preserve line breaks

    if not message:
        await update.message.reply_text("Give me a message to broadcast!")
        return

    sent = 0
    for user_id in init.user_details.keys():
        try:
            await safe_tele_func_call(
                context.bot.send_message,
                chat_id=user_id,
                text=message,
                parse_mode="Markdown"  # preserves bold, italic, inline code
            )
            sent += 1
            await asyncio.sleep(0.1)  # avoid rate limits
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")

    await update.message.reply_text(f"Broadcast sent to {sent} users ✅")
