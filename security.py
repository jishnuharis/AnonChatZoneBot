import os
import re
import asyncio
from telegram import Update
from telegram.constants import MessageEntityType
from telegram.error import Forbidden, Conflict, BadRequest, NetworkError, TimedOut, RetryAfter
from telegram.ext import ContextTypes, ApplicationHandlerStop

from html import escape as esc

import traceback
import time
import logging
from collections import defaultdict

import init
from saveNload import get_cached_telegram_handle, save_cached_telegram_handle

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
    if user.username:
        init.username_to_id[user.username.lower()] = user_id

    if user_id in init.user_details:
        init.user_details[user_id]["last_active"] = time.time()
        if user.username:
            init.user_details[user_id]["username"] = user.username.lower()

    from moderation import is_user_restricted
    restricted, reason, remaining = is_user_restricted(user_id)
    if restricted:
        remaining_str = format_duration(remaining or 0)
        await safe_reply(
            update,
            "⛔ <b>You are restricted from using this bot.</b>\n\n"
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


_HOMOGLYPH_MAP = {
    'а': 'a', 'в': 'b', 'с': 'c', 'е': 'e', 'о': 'o', 'р': 'p', 'т': 't', 'х': 'x', 'у': 'y',
    'А': 'A', 'В': 'B', 'С': 'C', 'Е': 'E', 'О': 'O', 'Р': 'P', 'Т': 'T', 'Х': 'X', 'У': 'Y',
}

_URL_ONLY_REGEX = re.compile(
    r"(?i)\b(?:https?://|ftp://|www\.)[^\s/$.?#].[^\s]*"
    r"|(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|edu|gov|io|me|co|xyz|info|biz|ru|in|app|site|online|tech|link|live|top|gg|club|vip|dev|ai|cc|to|ly|pro|store|space|agency|cloud|social|tv|page|click)\b"
    r"|(?:t|telegram)\.me/[a-zA-Z0-9_+]+"
    r"|tg://[^\s]+"
    r"|\b[a-zA-Z0-9-]+\s*\.\s*(?:com|org|net|io|me|xyz|app|site|top|gg|club|vip|dev|ai|to|ly)\b"
)

_URL_REGEX = re.compile(
    _URL_ONLY_REGEX.pattern + r"|@[a-zA-Z0-9_]{3,}"
)

# Obfuscated dot notation: e.g. "t(dot)me", "google[dot]com", "site ( dot ) com"
_OBFUSCATED_DOT_REGEX = re.compile(
    r"(?i)\b[a-zA-Z0-9-]+\s*(?:\(|\{|\[)\s*dot\s*(?:\)|\}|\])\s*(?:com|org|net|xyz|me|io|app|site|top|to|ly|co)\b"
    r"|(?:t|tele|telegram|wa|whatsapp)\s*(?:\(|\{|\[|\.)\s*(?:dot|\.)?\s*(?:\)|\}|\])?\s*me\b"
)

# Social handle triggers without '@':
# 1. "tg: johndoe", "insta: cute_girl", "wa: +123...", "snap: xxx", "sc: xxx"
_SOCIAL_HANDLE_PREFIX_REGEX = re.compile(
    r"(?i)\b(?:tg|tele|telegram|insta|ig|instagram|snap|sc|snapchat|wa|whatsapp|kik|discord|dc|tiktok|tt|twt|twitter)\s*[:=\-–—]\s*([a-zA-Z0-9_.-]{3,32})\b"
)

# 2. Intent sentences: "my tg is johndoe", "my telegram username is alex99", "add me on snap xxx", "find me on tg xxx"
_SOCIAL_INTENT_REGEX = re.compile(
    r"(?i)\bmy\s+(?:(?:tg|tele|telegram|insta|ig|instagram|snap|sc|snapchat|wa|whatsapp|discord|dc|tiktok|tt)\s+)?(?:user|username|handle|id|tag|name)?\s*(?:is|:)\s*([a-zA-Z0-9_.-]{3,32})\b"
    r"|\b(?:add|find|hit|reach|dm|message|msg|text)\s+(?:me\s+)?(?:on\s+)(?:tg|tele|telegram|insta|ig|instagram|snap|sc|snapchat|wa|whatsapp|discord|dc)\s+([a-zA-Z0-9_.-]{3,32})\b"
    r"|\b(?:my\s+)?(?:username|user|handle)\s*[:=\-–—]\s*([a-zA-Z0-9_.-]{3,32})\b"
    r"|\bmy\s+(?:username|user|handle)\s+is\s+([a-zA-Z0-9_.-]{3,32})\b"
)


# Phone numbers (7-15 digits formatted or spaced, e.g. +1 555 123 4567, 9876543210, 9 8 7 6 5 4 3 2 1 0)
_PHONE_REGEX = re.compile(
    r"(?:(?:\+|00)\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"
    r"|(?:\+?\d[\s.-]?){9,15}\d\b"
)

# Financial scam / phishing phrases
_SCAM_PHRASES_REGEX = re.compile(
    r"(?i)\b(?:crypto\s+investment|doubl(?:e|ing)\s+(?:money|crypto|stars|btc|eth)|earn\s+\$\d+\s+(?:daily|weekly|hourly)|free\s+(?:telegram\s+)?stars\s+bot|send\s+stars\s+get|free\s+crypto|dm\s+for\s+leaks|paid\s+content\s+leak)\b"
    r"|(?:bit\.ly|tinyurl\.com|is\.gd|cutt\.ly|rb\.gy)/[a-zA-Z0-9]+"
    r"|(?:t|telegram)\.me/\+[a-zA-Z0-9_-]+"
)


_FILE_EXT_REGEX = re.compile(r"\.(?:pdf|png|jpe?g|gif|docx?|zip|txt|mp[34]|csv|json|py|html)\b", re.IGNORECASE)

# Handles with letters, underscore, and digits (e.g. super_storm5, that_cool_guy_67, alex_99, 7_killer)
_HANDLE_TOKEN_REGEX = re.compile(
    r"(?i)(?<!\w)(?:"
    r"@[a-zA-Z0-9_]{3,32}"
    r"|(?:tg|tele|telegram|insta|ig|instagram|snap|sc|snapchat|wa|whatsapp|kik|discord|dc)\s*[:=\-–—]\s*[a-zA-Z0-9_.-]{3,32}"
    r"|[a-zA-Z0-9]+_[a-zA-Z0-9_]*\d[a-zA-Z0-9_]*"
    r"|[a-zA-Z0-9_]*\d[a-zA-Z0-9_]*_[a-zA-Z0-9]+"
    r")(?!\w)"
)

# Telegram bot usernames strictly end in "bot" or "_bot" (e.g. AnonChatZoneBot, FreeStarsBot)
_BOT_HANDLE_REGEX = re.compile(r"(?i)\b[a-zA-Z0-9_]{3,32}(?:bot|_bot)\b")

# Whitelist of legitimate English words and compound words ending in 'bot' / 'bots'
SAFE_BOT_WORDS = {
    "bot", "bots", "robot", "robots", "chatbot", "chatbots", "aimbot", "aimbots",
    "spambot", "spambots", "abbot", "turbot", "talbot", "sabot", "jabot", "cabot",
    "burbot", "chabot", "jarbot", "tarbot", "autobot", "autobots", "nanobot", "nanobots", "hubot"
}

_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_WORDS_FILE = os.path.join(_DATA_DIR, "english_words_50k.txt")

# English dictionary database loaded into memory for 0ms lookup, persisted on disk across reboots
ENGLISH_WORDS = set(SAFE_BOT_WORDS)
if os.path.exists(_WORDS_FILE):
    try:
        with open(_WORDS_FILE, "r", encoding="utf-8") as _f:
            ENGLISH_WORDS.update(line.strip().lower() for line in _f if line.strip())
    except Exception as _e:
        logger.warning(f"Could not load english words dictionary: {_e}")


def is_bot_candidate(token: str) -> bool:
    """Returns True if token looks like a Telegram bot handle and is not in safe dictionary."""
    if not token:
        return False
    clean = token.lower().strip("@.,!?:;\"'()[]{}")
    if clean in SAFE_BOT_WORDS or clean in ENGLISH_WORDS:
        return False
    if len(clean) < 4 or len(clean) > 35:
        return False
    if not (clean.endswith("bot") or clean.endswith("_bot")):
        return False
    return True


async def verify_telegram_handle(handle: str, bot=None) -> bool:
    """
    Validates a handle against persistent cache and live Telegram API:
    1. Checks in-memory & PostgreSQL cache (verified_telegram_handles).
    2. If not cached and `bot` is available, calls bot.get_chat(f"@{clean_handle}") with 0.8s timeout.
    3. Persists result in DB & memory so future checks take 0ms and survive reboots.
    4. If no bot is available (offline/mock), falls back to syntax validity.
    """
    clean_handle = handle.lstrip("@").strip()
    if not clean_handle:
        return False

    cached = await get_cached_telegram_handle(clean_handle)
    if cached is not None:
        is_valid, _ = cached
        return is_valid

    if not bot or not hasattr(bot, "get_chat"):
        return True

    try:
        chat = await asyncio.wait_for(bot.get_chat(f"@{clean_handle}"), timeout=0.8)
        chat_type = str(getattr(chat, "type", "bot") or "bot")
        await save_cached_telegram_handle(clean_handle, is_valid=True, chat_type=chat_type)
        return True
    except BadRequest as e:
        err = str(e).lower()
        if "chat not found" in err or "username not found" in err or "invalid username" in err:
            await save_cached_telegram_handle(clean_handle, is_valid=False, chat_type="")
            return False
        await save_cached_telegram_handle(clean_handle, is_valid=True, chat_type="unknown")
        return True
    except Exception as e:
        logger.debug(f"verify_telegram_handle({clean_handle}) notice: {e}")
        return True


def _deobfuscate_text(text: str) -> str:
    """Removes zero-width characters and maps homoglyphs."""
    if not text:
        return ""
    cleaned = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    for cyr, lat in _HOMOGLYPH_MAP.items():
        cleaned = cleaned.replace(cyr, lat)
    return cleaned


def is_scam_or_phishing_text(text: str) -> bool:
    """Returns True if text contains blatant financial scam, doubling, or malicious shortener phrases."""
    if not text:
        return False
    norm = _deobfuscate_text(text)
    return bool(_SCAM_PHRASES_REGEX.search(norm))


def is_scam_or_phishing_message(msg) -> bool:
    """Returns True if message or caption contains phishing or financial scam phrases."""
    if not msg:
        return False
    text_to_check = f"{getattr(msg, 'text', '') or ''} {getattr(msg, 'caption', '') or ''}"
    return is_scam_or_phishing_text(text_to_check)


def contains_prohibited_contact(text: str) -> bool:
    """
    Returns True if text contains links, handles (with or without @),
    bot usernames (e.g. AnonChatZoneBot), obfuscated dots, formatted/spaced phone numbers,
    or handle signatures.
    """
    if not text:
        return False
    norm = _deobfuscate_text(text)

    if _URL_REGEX.search(norm):
        return True
    if _OBFUSCATED_DOT_REGEX.search(norm):
        return True
    if _SOCIAL_HANDLE_PREFIX_REGEX.search(norm):
        return True
    if _SOCIAL_INTENT_REGEX.search(norm):
        return True
    if _PHONE_REGEX.search(norm):
        return True

    # If it's a file, don't flag as handle
    if not _FILE_EXT_REGEX.search(norm):
        if _HANDLE_TOKEN_REGEX.search(norm):
            return True
        for m in _BOT_HANDLE_REGEX.finditer(norm):
            if is_bot_candidate(m.group(0)):
                return True

    return False


def contains_link(msg) -> bool:
    """
    Returns True if the message or caption contains any URL, Telegram link,
    masked link entity, Telegram @username handle, off-platform contact handle
    (even without @), or formatted/spaced phone numbers.
    """
    if not msg:
        return False

    entities = []
    if getattr(msg, "entities", None):
        entities.extend(msg.entities)
    if getattr(msg, "caption_entities", None):
        entities.extend(msg.caption_entities)

    for ent in entities:
        ent_type = getattr(ent, "type", "")
        if ent_type in ("url", "text_link", "mention", MessageEntityType.URL, MessageEntityType.TEXT_LINK, MessageEntityType.MENTION):
            return True

    text_to_check = f"{getattr(msg, 'text', '') or ''} {getattr(msg, 'caption', '') or ''}"
    return contains_prohibited_contact(text_to_check)


async def sanitize_free_message(msg, caption=None, bot=None):
    """
    Evaluates message/caption for free-tier link and handle restrictions.
    Returns:
        (status, filtered_text, filtered_caption)
        status in ("CLEAN", "BLOCKED", "MASKED")
    - Under 6 words (< 6 words):
        Any handle, bot username, link, or asking-to-be-added is BLOCKED.
    - 6 or more words (>= 6 words):
        Embedded handles are masked in-place to '[handle hidden 🔒]',
        and candidate bot handles are masked in-place to '[bot hidden 🔒]',
        allowing jokes/banter to deliver without exposing off-platform contacts or bots.
        Explicit external web links/domains and phone numbers are strictly blocked.
    """
    if not msg:
        return "CLEAN", None, None

    raw_text = getattr(msg, "text", None)
    raw_caption = caption if caption is not None else getattr(msg, "caption", None)

    # 1. Check entities: actual URL entities are strictly blocked for free tier
    entities = []
    if getattr(msg, "entities", None):
        entities.extend(msg.entities)
    if getattr(msg, "caption_entities", None):
        entities.extend(msg.caption_entities)
    has_url_entity = any(
        getattr(ent, "type", "") in ("url", "text_link", MessageEntityType.URL, MessageEntityType.TEXT_LINK)
        for ent in entities
    )
    if has_url_entity:
        return "BLOCKED", raw_text, raw_caption

    # 2. Strict external URLs, obfuscated dots, or phone numbers are ALWAYS blocked for free tier
    for t in (raw_text, raw_caption):
        if not t:
            continue
        norm = _deobfuscate_text(t)
        if _URL_ONLY_REGEX.search(norm) or _OBFUSCATED_DOT_REGEX.search(norm) or _PHONE_REGEX.search(norm):
            return "BLOCKED", raw_text, raw_caption

    # 3. Find candidate bot tokens that are valid Telegram handles
    async def _get_valid_bots(txt: str):
        if not txt:
            return set()
        norm = _deobfuscate_text(txt)
        candidates = set()
        for m in _BOT_HANDLE_REGEX.finditer(norm):
            tok = m.group(0)
            if is_bot_candidate(tok):
                end = m.end()
                after = norm[end:end+10]
                if not (after.startswith(".") and _FILE_EXT_REGEX.match(after)):
                    candidates.add(tok)

        valid_bots = set()
        for cand in candidates:
            if bot is not None:
                is_valid = await verify_telegram_handle(cand, bot=bot)
                if is_valid:
                    valid_bots.add(cand)
            else:
                valid_bots.add(cand)
        return valid_bots

    text_bots = await _get_valid_bots(raw_text)
    caption_bots = await _get_valid_bots(raw_caption)

    # 4. Check for regular handle token pattern or verified bot candidates
    has_text_handle = bool(_HANDLE_TOKEN_REGEX.search(raw_text)) if raw_text else False
    has_cap_handle = bool(_HANDLE_TOKEN_REGEX.search(raw_caption)) if raw_caption else False

    has_any_threat = has_text_handle or has_cap_handle or bool(text_bots) or bool(caption_bots)
    if not has_any_threat:
        return "CLEAN", raw_text, raw_caption

    def _process_text(txt: str, valid_bots: set):
        if not txt:
            return "CLEAN", txt
        words = txt.strip().split()
        if len(words) < 6:
            # Short messages (< 6 words) or standalone drops are BLOCKED
            return "BLOCKED", txt

        # For >= 6 words: mask handles and bots in-place
        def _mask_handle(m):
            end = m.end()
            after = txt[end:end+10]
            if after.startswith(".") and _FILE_EXT_REGEX.match(after):
                return m.group(0)
            return "[handle hidden 🔒]"

        masked = _HANDLE_TOKEN_REGEX.sub(_mask_handle, txt)

        if valid_bots:
            def _mask_bot(m):
                token = m.group(0)
                if token in valid_bots or token.lower() in {b.lower() for b in valid_bots}:
                    end = m.end()
                    after = txt[end:end+10]
                    if after.startswith(".") and _FILE_EXT_REGEX.match(after):
                        return token
                    return "[bot hidden 🔒]"
                return token

            masked = _BOT_HANDLE_REGEX.sub(_mask_bot, masked)

        return "MASKED", masked

    status_t, filtered_text = _process_text(raw_text, text_bots) if raw_text else ("CLEAN", None)
    status_c, filtered_cap = _process_text(raw_caption, caption_bots) if raw_caption else ("CLEAN", None)

    if status_t == "BLOCKED" or status_c == "BLOCKED":
        return "BLOCKED", raw_text, raw_caption

    if status_t == "MASKED" or status_c == "MASKED":
        return "MASKED", filtered_text, filtered_cap

    return "BLOCKED", raw_text, raw_caption
