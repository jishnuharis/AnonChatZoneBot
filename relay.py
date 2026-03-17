# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import Forbidden

# from security import is_blocked_by  # Importing the func which checks if the bot is blocked

from commands.stop import stop  # Importing the function which stops the conversation between the users

from handlers.setup import handle_user_setup  # Importing the handler which handles the user setup
from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# FUnction which relays the message between the users
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.user_input_stage or user_id in init.edit_stage:  # Checking if the user is in user input stage or in the stage of editing the details
        await handle_user_setup(update, context)
        return
    if user_id in init.active_pairs:  # Checking if the user is in active pairs
        partner_id = init.active_pairs[user_id]
        msg = update.message
        try:  # Trying to relay the messages between the users
            if msg.text:
                await safe_tele_func_call(context.bot.send_message, chat_id=partner_id, text=msg.text)  # Relaying the message as plain text if it's just a message
            elif msg.sticker:
                await safe_tele_func_call(context.bot.send_sticker, chat_id=partner_id, sticker=msg.sticker.file_id)  # Relaying the message as sticker if it's a sticker
            elif msg.photo:
                await safe_tele_func_call(context.bot.send_photo, chat_id=partner_id, photo=msg.photo[-1].file_id, caption=msg.caption)  # Relaying the message as photo if it's a photo
            elif msg.video:
                await safe_tele_func_call(context.bot.send_video, chat_id=partner_id, video=msg.video.file_id, caption=msg.caption)  # Relaying the message as video if it's a video
            elif msg.video_note:
                await safe_tele_func_call(context.bot.send_video_note, chat_id=partner_id, video_note=msg.video_note.file_id)  # Relaying the message as voice note if it's a voice note
            elif msg.voice:
                await safe_tele_func_call(context.bot.send_voice, chat_id=partner_id, voice=msg.voice.file_id)  # Relaying the message as voice if it's a voice
            elif msg.audio:
                await safe_tele_func_call(context.bot.send_audio, chat_id=partner_id, audio=msg.audio.file_id, caption=msg.caption)  # Relaying the message as audio if it's a audio
            elif msg.document:
                await safe_tele_func_call(context.bot.send_document, chat_id=partner_id, document=msg.document.file_id, caption=msg.caption)  # Relaying the message as document if it's a document
            elif msg.animation:
                await safe_tele_func_call(context.bot.send_animation, chat_id=partner_id, animation=msg.animation.file_id, caption=msg.caption)  # Relaying the message as animation if it's an animation
        except Exception as e:  # Notifying that there was an issue relaying the message
            await safe_tele_func_call(update.message.reply_text, text="❌ *Failed to send message.*", parse_mode="Markdown")
            print(e)
    else:  # Notifying the user that they are not in a alive conversation
        await safe_tele_func_call(update.message.reply_text, text="❗ *You're not in a chat.* Use /find to connect.", parse_mode="Markdown")
