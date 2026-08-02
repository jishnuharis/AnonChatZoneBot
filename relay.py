# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import handle_user_setup  # Importing the handler which handles the user setup
from security import safe_tele_func_call
from media_privacy import extract_media, maybe_send_private, SUPPORTED_KINDS
from message import FAILED_TO_SEND_MESSAGE_TEXT, NOT_IN_CHAT_USE_FIND_INLINE_TEXT

import init  # Importing the bot credentials and users' details

# Cap on how many message-id mappings we keep per user, so a very long
# conversation can't grow message_map unbounded before /next or /stop clears it.
MAX_MAP_ENTRIES = 300


def _remember(a_id, a_msg_id, b_id, b_msg_id):
    """Records that message a_msg_id (in a_id's chat) and b_msg_id (in b_id's chat) are
    the same relayed message, in both directions, so a reply/reaction on either side
    can be traced back to the other."""
    for owner, local_id, other, other_id in ((a_id, a_msg_id, b_id, b_msg_id), (b_id, b_msg_id, a_id, a_msg_id)):
        bucket = init.message_map.setdefault(owner, {})
        bucket[local_id] = (other, other_id)
        if len(bucket) > MAX_MAP_ENTRIES:  # Trims the oldest entries so the map doesn't grow forever
            for stale_key in list(bucket.keys())[:len(bucket) - MAX_MAP_ENTRIES]:
                bucket.pop(stale_key, None)


def _resolve_reply(user_id, partner_id, msg):
    """If the user replied to a message, finds the matching message ID in the partner's
    chat so the relayed copy can be sent as a reply too."""
    if not msg.reply_to_message:
        return None
    mapped = init.message_map.get(user_id, {}).get(msg.reply_to_message.message_id)
    if mapped and mapped[0] == partner_id:
        return mapped[1]
    return None


# Function which relays the message between the users
async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.user_input_stage or user_id in init.edit_stage:  # Checking if the user is in user input stage or in the stage of editing the details
        await handle_user_setup(update, context)
        return
    if user_id in init.active_pairs:  # Checking if the user is in active pairs
        partner_id = init.active_pairs[user_id]
        msg = update.message

        # Photos/videos/voice/video notes can be sent in Privacy Mode by captioning them
        # "/private" (or sending a bare /private beforehand) - otherwise they relay normally
        # just like everything else, no interruption.
        kind, file_id, caption, duration = extract_media(msg)
        if kind in SUPPORTED_KINDS:
            handled = await maybe_send_private(update, context, partner_id, kind, file_id, caption, duration)
            if handled:
                return

        # If this message is a reply to something already relayed, mirror it as a reply
        # on the partner's side too. Falls back to a normal send if the target vanished.
        reply_to = _resolve_reply(user_id, partner_id, msg)

        try:  # Trying to relay the messages between the users
            sent = None
            if msg.text:
                sent = await safe_tele_func_call(context.bot.send_message, chat_id=partner_id, text=msg.text, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as plain text if it's just a message
            elif kind == "photo":
                sent = await safe_tele_func_call(context.bot.send_photo, chat_id=partner_id, photo=file_id, caption=caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as a photo
            elif kind == "video":
                sent = await safe_tele_func_call(context.bot.send_video, chat_id=partner_id, video=file_id, caption=caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as a video
            elif kind == "voice":
                sent = await safe_tele_func_call(context.bot.send_voice, chat_id=partner_id, voice=file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as a voice note
            elif kind == "video_note":
                sent = await safe_tele_func_call(context.bot.send_video_note, chat_id=partner_id, video_note=file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as a video note
            elif msg.sticker:
                sent = await safe_tele_func_call(context.bot.send_sticker, chat_id=partner_id, sticker=msg.sticker.file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as sticker if it's a sticker
            elif msg.audio:
                sent = await safe_tele_func_call(context.bot.send_audio, chat_id=partner_id, audio=msg.audio.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as audio if it's a audio
            elif msg.document:
                sent = await safe_tele_func_call(context.bot.send_document, chat_id=partner_id, document=msg.document.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as document if it's a document
            elif msg.animation:
                sent = await safe_tele_func_call(context.bot.send_animation, chat_id=partner_id, animation=msg.animation.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)  # Relaying the message as animation if it's an animation

            if sent is not None:  # Remembers the pairing so replies/reactions on this message can be relayed later
                _remember(user_id, msg.message_id, partner_id, sent.message_id)
        except Exception as e:  # Notifying that there was an issue relaying the message
            await safe_tele_func_call(update.message.reply_text, text=FAILED_TO_SEND_MESSAGE_TEXT, parse_mode="HTML")
            print(e)
    else:  # Notifying the user that they are not in an alive conversation
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_USE_FIND_INLINE_TEXT, parse_mode="HTML")


# Function which mirrors a reaction the user left on a relayed message onto the
# matching message in their partner's chat (an empty new_reaction means "removed").
async def relay_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction or not reaction.user:  # Ignores reactions with no identifiable user (e.g. anonymous channel reactions)
        return

    user_id = reaction.user.id
    partner_id = init.active_pairs.get(user_id)
    if not partner_id:  # Not currently paired with anyone, nothing to relay to
        return

    mapped = init.message_map.get(user_id, {}).get(reaction.message_id)
    if not mapped or mapped[0] != partner_id:  # The reacted-to message isn't a relayed message tied to the current partner
        return

    partner_msg_id = mapped[1]
    await safe_tele_func_call(
        context.bot.set_message_reaction,
        chat_id=partner_id,
        message_id=partner_msg_id,
        reaction=reaction.new_reaction,
    )
