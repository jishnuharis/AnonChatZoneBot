from telegram import Update
from telegram.ext import ContextTypes
import asyncio

from security import safe_tele_func_call
from handlers.rating import ask_for_rating

import init


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != int(init.OWNER):
        return

    message = update.message.text
    if message.lower().startswith("/broadcast"):
        message = message[len("/broadcast"):].lstrip()

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
                parse_mode="Markdown"
            )
            sent += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Failed to send to {user_id}: {e}")

    await update.message.reply_text(f"Broadcast sent to {sent} users ✅.")


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != int(init.OWNER):
        return

    message = update.message.text
    if message.lower().startswith("/connect"):
        message = message[len("/connect"):].strip()
    try:
        target_id = int(message)
    except ValueError:
        await update.message.reply_text("Give me a valid user id to connect.")
        return

    if target_id not in init.user_details:
        await update.message.reply_text("The target user isn't in our database.")
        return

    # if target_id == init.user_details[user_id]["partner_id"]:
    #     await update.message.reply_text("You are already connected to the target.")
    #     return

    targets_partner = init.user_details[target_id]["partner_id"]
    if targets_partner:
        init.active_pairs.pop(targets_partner)
        init.active_pairs.pop(target_id)
        init.user_details[targets_partner]["partner_id"] = None

        await safe_tele_func_call(context.bot.send_message, chat_id=targets_partner, text="⛔ *Your partner left the chat.*", parse_mode="Markdown")
        await ask_for_rating(context.bot, targets_partner, target_id)

    users_partner = init.user_details[user_id]["partner_id"]
    if users_partner:
        init.active_pairs.pop(users_partner)
        init.active_pairs.pop(user_id)
        init.user_details[users_partner]["partner_id"] = None

        await safe_tele_func_call(context.bot.send_message, chat_id=users_partner, text="⛔ *Your partner left the chat.*", parse_mode="Markdown")
        await ask_for_rating(context.bot, users_partner, user_id)

    init.active_pairs[user_id] = target_id
    init.active_pairs[target_id] = user_id
    uv1, uv2 = init.user_details[user_id]["votes"], init.user_details[target_id]["votes"]
    init.user_details[user_id]["partner_id"] = target_id
    init.user_details[target_id]["partner_id"] = user_id
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=f"🎯 *Found User.... Say Hi!!*\nRating: {uv2['up']} 👍 {uv2['down']} 👎\n/next - Next Chat\n/stop - Stop Chat", parse_mode="Markdown")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=f"🎯 *Someone Found You.... Say Hi!!*\nRating: {uv1['up']} 👍 {uv1['down']} 👎\n/next - Next Chat\n/stop - Stop Chat", parse_mode="Markdown")

    init.dirty_users.update([user_id, target_id])
