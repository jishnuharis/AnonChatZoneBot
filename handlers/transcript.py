import io
import time
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call


async def handle_export_transcript(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    parts = (query.data or "").split("|")
    if len(parts) < 2:
        return

    session_id = parts[1]
    messages = init.session_messages.get(session_id)

    if not messages:
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>Transcript expired or no messages were recorded for this chat.</b>",
            parse_mode="HTML",
        )
        return

    # Generate anonymized formatted text
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        "============================================================",
        "  AnonChatZoneBot — Anonymous Conversation Transcript",
        f"  Export Date: {now_str}",
        "  Privacy Guarantee: 100% Anonymized. No IDs or handles.",
        "============================================================",
        "",
    ]

    for sender_id, text, ts in messages:
        sender_label = "You" if sender_id == user_id else "Partner"
        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
        lines.append(f"[{time_str}] {sender_label}: {text}")

    lines.extend([
        "",
        "============================================================",
        "  End of Conversation — Saved from AnonChatZoneBot",
        "============================================================",
    ])

    transcript_content = "\n".join(lines)
    bio = io.BytesIO(transcript_content.encode("utf-8"))
    bio.name = f"AnonChat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    doc_sent = await safe_tele_func_call(
        context.bot.send_document,
        chat_id=user_id,
        document=bio,
        filename=bio.name,
        caption="📜 <b>Here is your saved conversation transcript!</b>\n<i>Keep this memory safe in your Saved Messages.</i>",
        parse_mode="HTML",
    )

    if doc_sent:
        await safe_tele_func_call(
            query.edit_message_text,
            text="✅ <b>Conversation transcript sent! Check your chat above.</b>",
            parse_mode="HTML",
        )
    else:
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>Could not deliver the transcript file. Please try again.</b>",
            parse_mode="HTML",
        )
