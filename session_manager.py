"""
Session Lifecycle and Presence Manager for AnonChatZoneBot.

Guarantees:
1. Silent chats remain connected indefinitely while users are genuinely connected.
   Inactivity/silence is NEVER treated as disconnection.
2. Graceful & unexpected disconnect handling (e.g. Forbidden: bot blocked by user).
3. Concurrency-safe single-teardown execution.
4. Automatic cleanup of games, pending requests, and message routing maps.
5. Integration with rating prompts and promotions.
"""

import asyncio
import logging
import time
from typing import Optional, Tuple
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call
from saveNload import create_chat_session_db, end_chat_session_db, is_blocked_pairwise
from games.registry import end_any_active_game
from games.game_requests import clear_pending_requests
from handlers.rating import ask_for_rating
from message import PARTNER_LEFT_CHAT_TEXT, CHAT_ENDED_TEXT
from subscription import is_subscribed

logger = logging.getLogger(__name__)

# Mutex to ensure session teardown runs exactly once even if both users /next or /stop concurrently
_teardown_lock = asyncio.Lock()

# Persistent keyboard below typing area during active chats
IN_CHAT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👋 Nudge", "⏱️ /status"],
        ["/next", "/stop"]
    ],
    resize_keyboard=True,
    is_persistent=True
)


def is_in_chat(user_id: int) -> bool:
    """Returns True if the user is in an active chat session."""
    return user_id in init.active_pairs


def get_partner(user_id: int) -> Optional[int]:
    """Returns the partner user_id for the given user, if paired."""
    return init.active_pairs.get(user_id)


def _record_recent_partner(user1: int, user2: int):
    """Tracks recently matched partners to prevent immediate rematches."""
    for u, p in ((user1, user2), (user2, user1)):
        history = init.recent_partners.setdefault(u, [])
        if p in history:
            history.remove(p)
        history.append(p)
        if len(history) > 3:
            history.pop(0)


def _overlap_score(a: int, b: int) -> int:
    pa = init.user_details.get(a, {}).get("preferences", 0)
    pb = init.user_details.get(b, {}).get("preferences", 0)
    return bin(pa & pb).count("1")


def _partner_details_line(viewer_id: int, partner_id: int) -> str:
    if not is_subscribed(viewer_id):
        return ""
    partner = init.user_details.get(partner_id, {})
    gender = "Male" if partner.get("gender") == "M" else "Female" if partner.get("gender") == "F" else "Unknown"
    age = partner.get("age") or "Unknown"
    country = partner.get("country") or "Unknown"
    return f"\n<i>👤 {gender}, {age} — {country}</i>"


async def start_chat_session(context: ContextTypes.DEFAULT_TYPE, user1: int, user2: int) -> bool:
    """
    Atomically starts a new chat session between user1 and user2.
    Validates blocks, ban status, and active states.
    """
    # 1. Validation checks
    if user1 == user2 or is_in_chat(user1) or is_in_chat(user2):
        return False

    if await is_blocked_pairwise(user1, user2):
        logger.warning(f"Blocked match attempt prevented between {user1} and {user2}")
        return False

    session_id = await create_chat_session_db(user1, user2)

    init.active_pairs[user1] = user2
    init.active_pairs[user2] = user1
    init.active_sessions[user1] = session_id
    init.active_sessions[user2] = session_id

    init.user_details.setdefault(user1, init._default_user())["partner_id"] = user2
    init.user_details.setdefault(user2, init._default_user())["partner_id"] = user1
    init.dirty_users.update([user1, user2])

    _record_recent_partner(user1, user2)

    uv1 = (init.user_details[user1].get("votes") or {}) if isinstance(init.user_details.get(user1), dict) else {}
    uv2 = (init.user_details[user2].get("votes") or {}) if isinstance(init.user_details.get(user2), dict) else {}
    if not isinstance(uv1, dict):
        uv1 = {"up": 0, "down": 0}
    if not isinstance(uv2, dict):
        uv2 = {"up": 0, "down": 0}

    shared = _overlap_score(user1, user2)
    shared_note = f"\n<i>You have {shared} shared interest{'s' if shared != 1 else ''}!</i> 🏷️" if shared else ""

    details1 = _partner_details_line(user1, user2)
    details2 = _partner_details_line(user2, user1)

    now = time.time()
    init.last_activity[user1] = now
    init.last_activity[user2] = now

    msg1 = await safe_tele_func_call(
        context.bot.send_message, chat_id=user1,
        text=f"🎯 <b>Found someone.... Say hi!!</b>\n<i>Rating:</i> {uv2.get('up', 0)} 👍 {uv2.get('down', 0)} 👎{shared_note}{details1}\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>",
        parse_mode="HTML",
        reply_markup=IN_CHAT_KEYBOARD,
    )
    if msg1 is None:
        # User1 blocked the bot - handle transport disconnect immediately!
        logger.info(f"User {user1} blocked bot during match creation. Aborting session.")
        await end_chat_session(context, user1, reason="transport_disconnect", notify_initiator=False, notify_partner=True)
        return False

    msg2 = await safe_tele_func_call(
        context.bot.send_message, chat_id=user2,
        text=f"🎯 <b>Found someone.... Say hi!!</b>\n<i>Rating:</i> {uv1.get('up', 0)} 👍 {uv1.get('down', 0)} 👎{shared_note}{details2}\n/next <i>- Next Chat</i>\n/stop <i>- Stop Chat</i>",
        parse_mode="HTML",
        reply_markup=IN_CHAT_KEYBOARD,
    )
    if msg2 is None:
        # User2 blocked the bot
        logger.info(f"User {user2} blocked bot during match creation. Aborting session.")
        await end_chat_session(context, user2, reason="transport_disconnect", notify_initiator=False, notify_partner=True)
        return False

    return True


async def end_chat_session(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    reason: str = "normal",
    notify_initiator: bool = True,
    notify_partner: bool = True,
) -> Optional[int]:
    """
    Safely and atomically tears down an active chat session.
    Guarantees no race conditions if both users leave concurrently.
    """
    async with _teardown_lock:
        if user_id not in init.active_pairs:
            return None

        partner = init.active_pairs.pop(user_id, None)
        if partner:
            init.active_pairs.pop(partner, None)

        session_id = init.active_sessions.pop(user_id, None)
        if partner:
            init.active_sessions.pop(partner, None)

        # Clear in-memory routing map to free memory
        init.message_map.pop(user_id, None)
        if partner:
            init.message_map.pop(partner, None)

        init.last_activity.pop(user_id, None)
        if partner:
            init.last_activity.pop(partner, None)

        if user_id in init.user_details:
            init.user_details[user_id]["partner_id"] = None
        if partner and partner in init.user_details:
            init.user_details[partner]["partner_id"] = None

        init.dirty_users.add(user_id)
        if partner:
            init.dirty_users.add(partner)

    # Teardown games & pending requests
    await end_any_active_game(context, user_id)
    if partner:
        await end_any_active_game(context, partner)

    clear_pending_requests(user_id)
    if partner:
        clear_pending_requests(partner)

    # Persist session termination in PostgreSQL
    if session_id:
        try:
            await end_chat_session_db(session_id, reason)
        except Exception as e:
            logger.error(f"Error persisting session end for {session_id}: {e}")

    # Dispatch notifications
    if partner and notify_partner:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=partner,
            text=PARTNER_LEFT_CHAT_TEXT,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
    if notify_initiator:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user_id,
            text=CHAT_ENDED_TEXT,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )

    # Solicit ratings
    if partner:
        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)

    # Trigger potential sponsor / promotion display
    try:
        from promotions.service import maybe_show_promotion
        await maybe_show_promotion(context.bot, user_id)
        if partner:
            await maybe_show_promotion(context.bot, partner)
    except Exception as e:
        logger.debug(f"Promotion display check notice: {e}")

    return partner


async def handle_transport_disconnect(context: ContextTypes.DEFAULT_TYPE, disconnected_user_id: int):
    """
    Called when Telegram API returns Forbidden (user blocked bot) or ChatNotFound.
    Cleanly ends the session and notifies the partner without hanging.
    """
    logger.info(f"Transport disconnect detected for user {disconnected_user_id} (bot blocked / deactivated).")
    await end_chat_session(
        context,
        disconnected_user_id,
        reason="user_blocked_bot",
        notify_initiator=False,
        notify_partner=True,
    )
