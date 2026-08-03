from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import handle_user_setup
from security import safe_tele_func_call
from media_privacy import extract_media, maybe_send_private, split_private_caption, SUPPORTED_KINDS
from message import FAILED_TO_SEND_MESSAGE_TEXT, NOT_IN_CHAT_USE_FIND_INLINE_TEXT, MEDIA_DAILY_LIMIT_REACHED_TEXT
from subscription import is_subscribed, has_daily_credit, consume_daily_credit, daily_credit_limit

import init

MAX_MAP_ENTRIES = 300

_KIND_LABELS = {"photo": "photo", "video": "video", "voice": "voice note", "video_note": "video note"}


def _remember(a_id, a_msg_id, b_id, b_msg_id):
    for owner, local_id, other, other_id in ((a_id, a_msg_id, b_id, b_msg_id), (b_id, b_msg_id, a_id, a_msg_id)):
        bucket = init.message_map.setdefault(owner, {})
        bucket[local_id] = (other, other_id)
        if len(bucket) > MAX_MAP_ENTRIES:
            for stale_key in list(bucket.keys())[:len(bucket) - MAX_MAP_ENTRIES]:
                bucket.pop(stale_key, None)


def _resolve_reply(user_id, partner_id, msg):
    if not msg.reply_to_message:
        return None
    mapped = init.message_map.get(user_id, {}).get(msg.reply_to_message.message_id)
    if mapped and mapped[0] == partner_id:
        return mapped[1]
    return None


async def relay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in init.user_input_stage or user_id in init.edit_stage:
        await handle_user_setup(update, context)
        return
    if user_id in init.active_pairs:
        partner_id = init.active_pairs[user_id]
        msg = update.message

        kind, file_id, caption, duration = extract_media(msg)
        if kind in SUPPORTED_KINDS:
            handled = await maybe_send_private(update, context, partner_id, kind, file_id, caption, duration)
            if handled:
                return
            _, caption = split_private_caption(caption)

        if kind in SUPPORTED_KINDS and not is_subscribed(user_id) and not has_daily_credit(user_id):
            await safe_tele_func_call(
                update.message.reply_text,
                text=MEDIA_DAILY_LIMIT_REACHED_TEXT.format(limit=daily_credit_limit(user_id), kind=_KIND_LABELS.get(kind, "media")),
                parse_mode="HTML",
            )
            return

        reply_to = _resolve_reply(user_id, partner_id, msg)

        try:
            sent = None
            if msg.text:
                sent = await safe_tele_func_call(context.bot.send_message, chat_id=partner_id, text=msg.text, reply_to_message_id=reply_to, allow_sending_without_reply=True)
            elif kind == "photo":
                sent = await safe_tele_func_call(context.bot.send_photo, chat_id=partner_id, photo=file_id, caption=caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)
                if sent and not is_subscribed(user_id):
                    consume_daily_credit(user_id)
            elif kind == "video":
                sent = await safe_tele_func_call(context.bot.send_video, chat_id=partner_id, video=file_id, caption=caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)
                if sent and not is_subscribed(user_id):
                    consume_daily_credit(user_id)
            elif kind == "voice":
                sent = await safe_tele_func_call(context.bot.send_voice, chat_id=partner_id, voice=file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)
                if sent and not is_subscribed(user_id):
                    consume_daily_credit(user_id)
            elif kind == "video_note":
                sent = await safe_tele_func_call(context.bot.send_video_note, chat_id=partner_id, video_note=file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)
                if sent and not is_subscribed(user_id):
                    consume_daily_credit(user_id)
            elif msg.sticker:
                sent = await safe_tele_func_call(context.bot.send_sticker, chat_id=partner_id, sticker=msg.sticker.file_id, reply_to_message_id=reply_to, allow_sending_without_reply=True)
            elif msg.audio:
                sent = await safe_tele_func_call(context.bot.send_audio, chat_id=partner_id, audio=msg.audio.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)
            elif msg.document:
                sent = await safe_tele_func_call(context.bot.send_document, chat_id=partner_id, document=msg.document.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)
            elif msg.animation:
                sent = await safe_tele_func_call(context.bot.send_animation, chat_id=partner_id, animation=msg.animation.file_id, caption=msg.caption, reply_to_message_id=reply_to, allow_sending_without_reply=True)

            if sent is not None:
                _remember(user_id, msg.message_id, partner_id, sent.message_id)
        except Exception as e:
            await safe_tele_func_call(update.message.reply_text, text=FAILED_TO_SEND_MESSAGE_TEXT, parse_mode="HTML")
            print(e)
    else:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_USE_FIND_INLINE_TEXT, parse_mode="HTML")


async def relay_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reaction = update.message_reaction
    if not reaction or not reaction.user:
        return

    user_id = reaction.user.id
    partner_id = init.active_pairs.get(user_id)
    if not partner_id:
        return

    mapped = init.message_map.get(user_id, {}).get(reaction.message_id)
    if not mapped or mapped[0] != partner_id:
        return

    partner_msg_id = mapped[1]
    await safe_tele_func_call(
        context.bot.set_message_reaction,
        chat_id=partner_id,
        message_id=partner_msg_id,
        reaction=reaction.new_reaction,
    )
