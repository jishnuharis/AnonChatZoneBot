from telegram import Update
from telegram.error import Forbidden, Conflict, BadRequest, NetworkError, TimedOut, RetryAfter
from telegram.ext import ContextTypes, ApplicationHandlerStop

from html import escape as esc

import traceback
import time
import logging
from collections import defaultdict

import init

logger = logging.getLogger(__name__)

# Error alert rate limiting (at most 1 notification per 15s to OWNER to prevent Telegram rate limit flood)
_last_error_alert_time = 0.0
_suppressed_error_count = 0

# In-memory token bucket rate limiter per user for anti-spam
_user_msg_times = defaultdict(list)
MSG_RATE_LIMIT = 5  # max messages per second
MSG_RATE_WINDOW = 1.0


def check_rate_limit(user_id: int) -> bool:
    """Returns True if within rate limit, False if spamming."""
    now = time.time()
    history = _user_msg_times[user_id]
    # Prune old timestamps
    _user_msg_times[user_id] = [t for t in history if now - t < MSG_RATE_WINDOW]
    if len(_user_msg_times[user_id]) >= MSG_RATE_LIMIT:
        return False
    _user_msg_times[user_id].append(now)
    return True


async def safe_tele_func_call(caller, *args, raise_on_forbidden: bool = False, **kwargs):
    """
    Safely executes a Telegram API call.
    Catches Forbidden, BadRequest ('message is not modified'), and temporary network issues.
    """
    try:
        return await caller(*args, **kwargs)
    except Forbidden as e:
        logger.info(f"Forbidden error encountered on Telegram API call: {e}")
        if raise_on_forbidden:
            raise
        return None
    except BadRequest as e:
        err_msg = str(e).lower()
        if (
            "message is not modified" in err_msg
            or "message to delete not found" in err_msg
            or "message can't be deleted" in err_msg
            or "message to edit not found" in err_msg
            or "message can't be edited" in err_msg
        ):
            return None
        logger.warning(f"BadRequest on Telegram API call: {e}")
        raise
    except (NetworkError, TimedOut) as e:
        logger.warning(f"Temporary network error on Telegram API call: {e}")
        return None
    except RetryAfter as e:
        logger.warning(f"Hit Telegram RetryAfter ({e.retry_after}s) on call")
        return None


async def safe_reply(update: Update, text: str, **kwargs):
    kwargs.setdefault("parse_mode", "HTML")
    context = kwargs.pop("context", None)
    answer_query = kwargs.pop("answer_query", False)

    # 1. Message update
    if getattr(update, "message", None) is not None and hasattr(update.message, "reply_text"):
        return await safe_tele_func_call(update.message.reply_text, text=text, **kwargs)

    # 2. CallbackQuery update
    if getattr(update, "callback_query", None) is not None:
        query = update.callback_query
        if answer_query and hasattr(query, "answer"):
            await safe_tele_func_call(query.answer)
        query_msg = getattr(query, "message", None)
        if query_msg is not None and hasattr(query_msg, "reply_text"):
            return await safe_tele_func_call(query_msg.reply_text, text=text, **kwargs)

    # 3. Effective message fallback
    eff_msg = getattr(update, "effective_message", None)
    if eff_msg is not None and hasattr(eff_msg, "reply_text"):
        return await safe_tele_func_call(eff_msg.reply_text, text=text, **kwargs)

    # 4. Fallback to direct bot.send_message
    bot = kwargs.pop("bot", None)
    if not bot and context and hasattr(context, "bot"):
        bot = context.bot
    if not bot and hasattr(update, "get_bot"):
        try:
            bot = update.get_bot()
        except Exception:
            bot = None
    if not bot:
        bot = getattr(update, "_bot", None)

    chat_id = None
    if getattr(update, "effective_chat", None) is not None:
        chat_id = getattr(update.effective_chat, "id", None)
    if chat_id is None and getattr(update, "effective_user", None) is not None:
        chat_id = getattr(update.effective_user, "id", None)

    if bot and chat_id is not None:
        return await safe_tele_func_call(bot.send_message, chat_id=chat_id, text=text, **kwargs)


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
    """
    Early gate handler running in group -2.
    Halts processing immediately if user is restricted or banned.
    """
    user = update.effective_user
    if not user:
        return
    user_id = user.id

    from moderation import is_user_restricted
    restricted, reason, remaining = is_user_restricted(user_id)
    if restricted:
        remaining_str = format_duration(remaining or 0)
        await safe_reply(
            update,
            "⛔ <b>You are restricted from using this bot.</b>\n"
            f"<i>Reason:</i> <code>{esc(str(reason))}</code>\n"
            f"<i>Time left:</i> <code>{esc(remaining_str)}</code>\n\n"
            "<i>If you think this is a mistake, reach out to a bot admin to sort it out.</i>",
            answer_query=True,
        )
        raise ApplicationHandlerStop


async def global_error_handler(update, context):
    """
    Catches unhandled errors, logs them structured, and throttles admin notifications.
    """
    global _last_error_alert_time, _suppressed_error_count

    try:
        e = context.error
        if isinstance(e, Conflict):
            return
        if isinstance(e, BadRequest) and "message is not modified" in str(e).lower():
            return

        logger.error(f"Global error caught: {type(e).__name__}: {e}", exc_info=e)

        now = time.time()
        # Throttle error messages sent to OWNER
        if now - _last_error_alert_time < 15.0:
            _suppressed_error_count += 1
            return

        _last_error_alert_time = now
        suppressed_notice = f"\n<i>(+{_suppressed_error_count} similar errors suppressed)</i>" if _suppressed_error_count > 0 else ""
        _suppressed_error_count = 0

        tb_list = traceback.extract_tb(e.__traceback__)
        text = "🚨 <b>Error caught</b>\n\n"
        text += f"<b>{esc(type(e).__name__)}:</b> {esc(str(e))}\n"

        if update and update.effective_user:
            text += f"\n👤 <b>User ID:</b> <code>{update.effective_user.id}</code>\n"

        for frame in reversed(tb_list):
            if "site-packages" not in frame.filename:
                text += (
                    f"\n📄 <b>File:</b> <code>{esc(frame.filename)}</code>:<code>{frame.lineno}</code>\n"
                    f"⚙️ <b>Function:</b> <code>{esc(frame.name)}</code>\n"
                    f"💻 <b>Code:</b> <code>{esc(frame.line or 'No source')}</code>"
                )
                break

        text += suppressed_notice

        if init.OWNER:
            try:
                owner_id = int(init.OWNER)
                await context.bot.send_message(chat_id=owner_id, text=text, parse_mode="HTML")
            except Exception as send_err:
                logger.debug(f"Could not deliver error to OWNER: {send_err}")
    except Exception as err:
        logger.error(f"Error inside the global error handler: {err}")
