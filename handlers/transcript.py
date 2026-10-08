import io
import html
import time
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call


def _build_html_transcript(messages, user_id: int) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    chat_rows = []
    for sender_id, text, ts in messages:
        is_me = (sender_id == user_id)
        sender_label = "You" if is_me else "Partner"
        time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S")
        safe_text = html.escape(text or "").replace("\n", "<br>")
        row_cls = "msg-row me" if is_me else "msg-row them"
        bubble_cls = "bubble me" if is_me else "bubble them"
        chat_rows.append(
            f'      <div class="{row_cls}">\n'
            f'        <div class="{bubble_cls}">\n'
            f'          <div class="sender">{sender_label}</div>\n'
            f'          <div class="text">{safe_text}</div>\n'
            f'          <div class="time">{time_str}</div>\n'
            f'        </div>\n'
            f'      </div>'
        )

    chat_body = "\n".join(chat_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AnonChatZone — Anonymous Conversation Transcript</title>
<style>
  :root {{
    --bg: #0e1621;
    --card: #17212b;
    --me-bubble: linear-gradient(135deg, #2b5278, #246bfd);
    --them-bubble: #242f3d;
    --text: #f5f5f5;
    --text-muted: #7f91a4;
    --border: #2b394a;
  }}
  @media (prefers-color-scheme: light) {{
    :root {{
      --bg: #f0f2f5;
      --card: #ffffff;
      --me-bubble: linear-gradient(135deg, #4fa3d1, #2481cc);
      --them-bubble: #e4e7eb;
      --text: #111b21;
      --text-muted: #667781;
      --border: #e0e4e8;
    }}
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif;
    line-height: 1.5;
    padding: 24px 12px;
    display: flex;
    justify-content: center;
  }}
  .container {{
    width: 100%;
    max-width: 680px;
    background: var(--card);
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    overflow: hidden;
    border: 1px solid var(--border);
  }}
  .header {{
    background: rgba(0,0,0,0.15);
    padding: 20px 16px;
    text-align: center;
    border-bottom: 1px solid var(--border);
  }}
  .header h1 {{
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  .header .meta {{
    font-size: 0.85rem;
    color: var(--text-muted);
  }}
  .header .badge {{
    display: inline-block;
    background: rgba(46, 204, 113, 0.15);
    color: #2ecc71;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin-top: 10px;
  }}
  .chat-box {{
    padding: 20px 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 250px;
  }}
  .msg-row {{
    display: flex;
    width: 100%;
  }}
  .msg-row.me {{
    justify-content: flex-end;
  }}
  .msg-row.them {{
    justify-content: flex-start;
  }}
  .bubble {{
    max-width: 82%;
    padding: 10px 14px;
    border-radius: 14px;
    word-break: break-word;
    box-shadow: 0 2px 5px rgba(0,0,0,0.15);
  }}
  .bubble.me {{
    background: var(--me-bubble);
    color: #ffffff;
    border-bottom-right-radius: 4px;
  }}
  .bubble.them {{
    background: var(--them-bubble);
    color: var(--text);
    border-bottom-left-radius: 4px;
  }}
  .sender {{
    font-size: 0.75rem;
    font-weight: 700;
    margin-bottom: 3px;
    opacity: 0.85;
  }}
  .text {{
    font-size: 0.95rem;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  .time {{
    font-size: 0.7rem;
    text-align: right;
    margin-top: 4px;
    opacity: 0.75;
  }}
  .footer {{
    padding: 14px 20px;
    text-align: center;
    font-size: 0.8rem;
    color: var(--text-muted);
    border-top: 1px solid var(--border);
    background: rgba(0,0,0,0.08);
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>AnonChatZone — Anonymous Conversation Transcript</h1>
    <div class="meta">Export Date: {now_str} • {len(messages)} messages</div>
    <div class="badge">Privacy Guarantee: 100% Anonymized. No IDs or handles.</div>
  </div>
  <div class="chat-box">
{chat_body}
  </div>
  <div class="footer">
    End of Conversation — Saved from AnonChatZoneBot
  </div>
</div>
</body>
</html>
"""


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

    # Generate styled HTML transcript with UTF-8 BOM encoding
    html_content = _build_html_transcript(messages, user_id)
    bio = io.BytesIO(html_content.encode("utf-8-sig"))
    bio.name = f"AnonChat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    doc_sent = await safe_tele_func_call(
        context.bot.send_document,
        chat_id=user_id,
        document=bio,
        filename=bio.name,
        caption=(
            "📜 <b>Here is your saved conversation transcript!</b>\n\n"
            "<i>Formatted with chat bubbles and full emoji support. Open in any browser!</i>"
        ),
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
