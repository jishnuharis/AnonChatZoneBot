import time
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from handlers.setup import check_user_profile
from message import (
    NOT_IN_CHAT_TEXT, SENT_PRIVACY_MODE_TEXT, PRIVACY_MODE_PLACEHOLDER_TEXT,
    PRIVACY_MEDIA_NO_LONGER_AVAILABLE_ALERT, PRIVACY_MEDIA_NO_LONGER_AVAILABLE_TEXT,
    NOT_FOR_YOU_ALERT, ALREADY_VIEWED_ALERT, ALREADY_VIEWED_TEXT, YOUR_MEDIA_VIEWED_TEXT,
    PRIVACY_MEDIA_EXPIRED_EDIT_TEXT, PRIVACY_MEDIA_EXPIRED_DM_TEXT, PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT,
)
from subscription import is_subscribed

import init

VIEW_LIFETIME = 45
EXPIRY = 24 * 3600
PRIVATE_FLAG_WINDOW = 5 * 60

SUPPORTED_KINDS = {"photo", "video", "voice", "video_note"}

_armed_until = {}


def extract_media(msg):
    if msg.photo:
        return "photo", msg.photo[-1].file_id, msg.caption, None
    if msg.video:
        return "video", msg.video.file_id, msg.caption, msg.video.duration
    if msg.voice:
        return "voice", msg.voice.file_id, None, msg.voice.duration
    if msg.video_note:
        return "video_note", msg.video_note.file_id, None, msg.video_note.duration
    return None, None, None, None


def split_private_caption(caption):
    if not caption:
        return False, caption
    stripped = caption.strip()
    lowered = stripped.lower()
    if lowered == "/private":
        return True, None
    if lowered.startswith("/private "):
        remainder = stripped[len("/private "):].strip()
        return True, (remainder or None)
    return False, caption


def arm_private_flag(user_id: int):
    _armed_until[user_id] = time.time() + PRIVATE_FLAG_WINDOW


def _consume_private_flag(user_id: int) -> bool:
    expiry = _armed_until.pop(user_id, None)
    return bool(expiry and time.time() < expiry)


async def maybe_send_private(update: Update, context: ContextTypes.DEFAULT_TYPE, partner_id, kind, file_id, caption, duration) -> bool:
    user_id = update.effective_user.id

    is_private, remaining_caption = split_private_caption(caption)
    if not is_private:
        is_private = _consume_private_flag(user_id)
        remaining_caption = caption
    else:
        _armed_until.pop(user_id, None)

    if not is_private:
        return False

    if not is_subscribed(user_id):
        await safe_tele_func_call(update.message.reply_text, text=PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT, parse_mode="HTML")
        return False

    token = str(uuid.uuid4())
    init.pending_media[token] = {
        "sender": user_id,
        "recipient": partner_id,
        "kind": kind,
        "file_id": file_id,
        "caption": remaining_caption,
        "duration": duration,
        "created_at": time.time(),
        "opened": False,
    }
    await safe_tele_func_call(update.message.reply_text, text=SENT_PRIVACY_MODE_TEXT, parse_mode="HTML")

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔒 Tap to view (once)", callback_data=f"viewonce|{token}")]])
    placeholder = await safe_tele_func_call(
        context.bot.send_message,
        chat_id=partner_id,
        text=PRIVACY_MODE_PLACEHOLDER_TEXT,
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    if placeholder:
        init.pending_media[token]["placeholder_chat"] = partner_id
        init.pending_media[token]["placeholder_msg"] = placeholder.message_id

    return True


@check_user_profile
async def handle_private_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_subscribed(user_id):
        await safe_tele_func_call(update.message.reply_text, text=PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT, parse_mode="HTML")
        return
    if user_id not in init.active_pairs:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return
    arm_private_flag(user_id)
    minutes = PRIVATE_FLAG_WINDOW // 60
    await safe_tele_func_call(
        update.message.reply_text,
        text=f"🔒 <b>Privacy Mode armed.</b>\n<i>Send a photo, video, voice or video note within the next {minutes} minutes and it'll go out in Privacy Mode.</i>",
        parse_mode="HTML",
    )


def _lifetime_for(entry) -> int:
    if entry["kind"] == "photo":
        return VIEW_LIFETIME
    return int(entry.get("duration") or 0) + VIEW_LIFETIME


async def handle_view_once(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    token = query.data.split("|", 1)[1]

    entry = init.pending_media.get(token)
    if not entry:
        await query.answer(PRIVACY_MEDIA_NO_LONGER_AVAILABLE_ALERT, show_alert=True)
        await safe_tele_func_call(query.edit_message_text, text=PRIVACY_MEDIA_NO_LONGER_AVAILABLE_TEXT, parse_mode="HTML")
        return

    if entry["recipient"] != user_id:
        await query.answer(NOT_FOR_YOU_ALERT, show_alert=True)
        return

    if entry["opened"]:
        await query.answer(ALREADY_VIEWED_ALERT, show_alert=True)
        await safe_tele_func_call(query.edit_message_text, text=ALREADY_VIEWED_TEXT, parse_mode="HTML")
        init.pending_media.pop(token, None)
        return

    await query.answer()
    entry["opened"] = True

    revealed = None
    if entry["kind"] == "photo":
        revealed = await safe_tele_func_call(context.bot.send_photo, chat_id=user_id, photo=entry["file_id"], caption=entry["caption"], protect_content=True, has_spoiler=True)
    elif entry["kind"] == "video":
        revealed = await safe_tele_func_call(context.bot.send_video, chat_id=user_id, video=entry["file_id"], caption=entry["caption"], protect_content=True, has_spoiler=True)
    elif entry["kind"] == "voice":
        revealed = await safe_tele_func_call(context.bot.send_voice, chat_id=user_id, voice=entry["file_id"], protect_content=True)
    elif entry["kind"] == "video_note":
        revealed = await safe_tele_func_call(context.bot.send_video_note, chat_id=user_id, video_note=entry["file_id"], protect_content=True)

    lifetime = _lifetime_for(entry)
    await safe_tele_func_call(
        query.edit_message_text,
        text=f"🔒 <i>Opened. This will disappear from the chat in {lifetime}s.</i>",
        parse_mode="HTML",
    )

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=entry["sender"],
        text=YOUR_MEDIA_VIEWED_TEXT,
        parse_mode="HTML",
    )

    if revealed:
        context.job_queue.run_once(
            _delete_revealed,
            when=lifetime,
            data={"chat_id": user_id, "message_id": revealed.message_id},
        )

    init.pending_media.pop(token, None)


async def _delete_revealed(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except Exception:
        pass


async def sweep_expired_media(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()

    stale_flags = [uid for uid, expiry in _armed_until.items() if now >= expiry]
    for uid in stale_flags:
        _armed_until.pop(uid, None)

    expired_tokens = [t for t, e in init.pending_media.items() if not e["opened"] and now - e["created_at"] > EXPIRY]
    for token in expired_tokens:
        entry = init.pending_media.pop(token, None)
        if not entry:
            continue
        placeholder_chat = entry.get("placeholder_chat")
        placeholder_msg = entry.get("placeholder_msg")
        if placeholder_chat and placeholder_msg:
            try:
                await context.bot.edit_message_text(chat_id=placeholder_chat, message_id=placeholder_msg, text=PRIVACY_MEDIA_EXPIRED_EDIT_TEXT)
            except Exception:
                pass
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=entry["sender"],
            text=PRIVACY_MEDIA_EXPIRED_DM_TEXT,
            parse_mode="HTML",
        )
