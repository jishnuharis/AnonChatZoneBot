from telegram import Update
from telegram.error import Forbidden, Conflict, BadRequest
from telegram.ext import ContextTypes, ApplicationHandlerStop

from html import escape as esc

import traceback
import time

import init


async def safe_tele_func_call(caller, *args, **kwargs):
    try:
        return await caller(*args, **kwargs)
    except Forbidden:
        return None
    except BadRequest as e:
        if "message is not modified" in str(e).lower():
            return None
        raise


async def safe_reply(update: Update, text: str, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    if update.callback_query:
        await safe_tele_func_call(update.callback_query.answer)
        await safe_tele_func_call(update.callback_query.message.reply_text, text, **kwargs)
    elif update.message:
        await safe_tele_func_call(update.message.reply_text, text, **kwargs)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


async def restriction_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    user_id = user.id

    details = init.user_details.get(user_id)
    if not details:
        return

    restricted_until = details.get("restricted_until")
    if restricted_until:
        now = time.time()
        if now < restricted_until:
            reason = details.get("restriction_reason") or "Violation of bot rules"
            remaining = format_duration(restricted_until - now)
            await safe_reply(
                update,
                "⛔ <b>You are restricted from using this bot.</b>\n"
                f"<i>Reason:</i> <code>{esc(str(reason))}</code>\n"
                f"<i>Time left:</i> <code>{esc(remaining)}</code>\n\n"
                "<i>If you think this is a mistake, reach out to a bot admin to sort it out.</i>",
            )
            raise ApplicationHandlerStop
        else:
            # Restriction has expired, clear it out
            details["restricted_until"] = None
            details["restriction_reason"] = None
            init.dirty_users.add(user_id)


async def global_error_handler(update, context):
    try:
        e = context.error

        if isinstance(e, Conflict):
            return
        if isinstance(e, BadRequest) and "message is not modified" in str(e).lower():
            return

        tb_list = traceback.extract_tb(e.__traceback__)

        text = "🚨 <b>Error caught</b>\n\n"
        text += f"<b>{esc(type(e).__name__)}:</b> {esc(str(e))}\n"

        if update and update.effective_user:
            text += f"\n👤 <b>User ID:</b> <code>{update.effective_user.id}</code>\n"

        for frame in reversed(tb_list):
            if "site-packages" not in frame.filename:
                file = frame.filename
                line = frame.lineno
                func = frame.name
                code = frame.line or "No source available"

                text += (
                    f"\n📄 <b>File:</b> <code>{esc(file)}</code>:<code>{line}</code>\n"
                    f"⚙️ <b>Function:</b> <code>{esc(func)}</code>\n"
                    f"💻 <b>Code:</b> <code>{esc(code)}</code>"
                )
                break

        await context.bot.send_message(chat_id=init.OWNER, text=text, parse_mode="HTML")
    except Exception as err:
        print("Error inside the error handler: ", err)
