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
import os
import json
import random
from typing import Optional, Tuple, List
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call
from saveNload import create_chat_session_db, end_chat_session_db, is_blocked_pairwise
from games.registry import end_any_active_game
from games.game_requests import clear_pending_requests
from handlers.rating import ask_for_rating
from message import PARTNER_LEFT_CHAT_TEXT, CHAT_ENDED_TEXT, PARTNER_FOUND_TEMPLATE
from subscription import is_subscribed

logger = logging.getLogger(__name__)

# Mutex to ensure session teardown runs exactly once even if both users /next or /stop concurrently
_teardown_lock = asyncio.Lock()

# In-Chat keyboard below typing area during active chats
IN_CHAT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["👋 Nudge your partner!"],
        ["🛑 Stop", "🎁 Gift", "⏭️ Next"],
        ["⭐ Subscription", "🎮 Games"],
    ],
    resize_keyboard=True,
    is_persistent=False,
)

# Idle keyboard below typing area when outside active chat
IDLE_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🔍 Find Partner"],
        ["⭐ Subscription", "👤 Profile"],
    ],
    resize_keyboard=True,
    is_persistent=False,
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


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ICEBREAKERS_FILE = os.path.join(DATA_DIR, "icebreakers.json")
TIPS_FILE = os.path.join(DATA_DIR, "tips.json")

_icebreakers_cache: List[str] = []
_tips_cache: List[str] = []


def _load_starters_content():
    global _icebreakers_cache, _tips_cache
    if os.path.exists(ICEBREAKERS_FILE):
        try:
            with open(ICEBREAKERS_FILE, "r", encoding="utf-8") as f:
                _icebreakers_cache = json.load(f)
        except Exception as e:
            logger.error(f"Error loading {ICEBREAKERS_FILE}: {e}")
    if os.path.exists(TIPS_FILE):
        try:
            with open(TIPS_FILE, "r", encoding="utf-8") as f:
                _tips_cache = json.load(f)
        except Exception as e:
            logger.error(f"Error loading {TIPS_FILE}: {e}")


# Initialize in-memory cache on import
_load_starters_content()

ICEBREAKERS = _icebreakers_cache
TIPS = _tips_cache


def get_random_starter_blockquote() -> str:
    """
    Returns a blockquote formatted string containing either an Icebreaker or a Tip (50% chance each).
    Format:
    <blockquote>💡 <b>Icebreaker:</b>
    {text}</blockquote>
    or
    <blockquote>💡 <b>Tip:</b>
    {text}</blockquote>
    """
    if random.random() < 0.5 and _icebreakers_cache:
        item = random.choice(_icebreakers_cache)
        return f"<blockquote>💡 <b>Icebreaker:</b>\n{item}</blockquote>"
    elif _tips_cache:
        item = random.choice(_tips_cache)
        return f"<blockquote>💡 <b>Tip:</b>\n{item}</blockquote>"
    elif _icebreakers_cache:
        item = random.choice(_icebreakers_cache)
        return f"<blockquote>💡 <b>Icebreaker:</b>\n{item}</blockquote>"
    else:
        return "<blockquote>💡 <b>Tip:</b>\nType /game while in a chat to play Tic-Tac-Toe, Trivia, or Rock-Paper-Scissors with your partner!</blockquote>"


def _build_shared_interests_line(user1: int, user2: int) -> str:
    p1 = init.user_details.get(user1, {}).get("preferences", 0) or 0
    p2 = init.user_details.get(user2, {}).get("preferences", 0) or 0
    overlap = p1 & p2
    shared_tags = []
    for i, (name, emoji) in enumerate(init.PREFERENCE_TAGS):
        if overlap & (1 << i):
            shared_tags.append(f"{emoji} {name}")

    if shared_tags:
        return f"{', '.join(shared_tags)}"
    else:
        return "<b>None</b> <i>(Maybe ask them yourself)</i>"


def _build_shared_interest_or_icebreaker(user1: int, user2: int) -> str:
    """Legacy helper maintained for test and backward compatibility."""
    interests = _build_shared_interests_line(user1, user2)
    return f"\n✨ <b>Shared Interests:</b> {interests}"


def _overlap_score(a: int, b: int) -> int:
    pa = init.user_details.get(a, {}).get("preferences", 0)
    pb = init.user_details.get(b, {}).get("preferences", 0)
    return bin(pa & pb).count("1")


def _partner_details_line(viewer_id: int, partner_id: int) -> str:
    if not is_subscribed(viewer_id):
        return ""
    partner = init.user_details.get(partner_id, {})
    g = partner.get("gender")
    gender = "Male 👨" if g == "M" else "Female 👩" if g == "F" else "Not specified"
    return f"\n👑 <i>VIP Peek: Partner is {gender}</i>"



async def start_chat_session(
    context: ContextTypes.DEFAULT_TYPE,
    user1: int,
    user2: int,
    is_friend_connection: bool = False,
    friend_name_1: str = "",
    friend_name_2: str = "",
    is_admin_connect: bool = False,
) -> bool:
    """
    Atomically starts a new chat session between user1 and user2.
    Validates blocks, ban status, and active states.
    """
    # 1. Validation checks
    if user1 == user2 or is_in_chat(user1) or is_in_chat(user2):
        return False

    if not is_admin_connect and await is_blocked_pairwise(user1, user2):
        logger.warning(f"Blocked match attempt prevented between {user1} and {user2}")
        return False

    session_id = await create_chat_session_db(user1, user2)

    init.active_pairs[user1] = user2
    init.active_pairs[user2] = user1
    init.active_sessions[user1] = session_id
    init.active_sessions[user2] = session_id

    # Initialize ephemeral transcript message buffer
    init.session_messages[session_id] = []

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

    shared_interests = _build_shared_interests_line(user1, user2)
    starter_blockquote = get_random_starter_blockquote()

    details1 = _partner_details_line(user1, user2)
    details2 = _partner_details_line(user2, user1)

    now = time.time()
    init.last_activity[user1] = now
    init.last_activity[user2] = now
    init.session_start_times[user1] = now
    init.session_start_times[user2] = now

    if is_admin_connect:
        text1 = f"🎯 <b>Connected to target user! Say hi!</b> 👋\n\n/next <i>- Next</i>\n/stop <i>- Stop</i>"
        text2 = f"🎯 <b>Someone found you.... Say hi!!</b>\n\n/next <i>- Next</i>\n/stop <i>- Stop</i>"
    elif is_friend_connection:
        text1 = (
            f"🎉 <b>You are now connected with your anonymous friend {friend_name_1 or 'Friend'}!</b>\n\n"
            f"Say hi! 👋\n"
            f"✨ <b>Shared Interests:</b> {shared_interests}\n\n"
            f"{starter_blockquote}\n\n"
            f"───────────────\n"
            f"⏭️ /next <i>— Next Chat</i>\n"
            f"🛑 /stop <i>— Leave Chat</i>"
        )
        text2 = (
            f"🎉 <b>You are now connected with your anonymous friend {friend_name_2 or 'Friend'}!</b>\n\n"
            f"Say hi! 👋\n"
            f"✨ <b>Shared Interests:</b> {shared_interests}\n\n"
            f"{starter_blockquote}\n\n"
            f"───────────────\n"
            f"⏭️ /next <i>— Next Chat</i>\n"
            f"🛑 /stop <i>— Leave Chat</i>"
        )
    else:
        text1 = PARTNER_FOUND_TEMPLATE.format(
            rating_up=uv2.get("up", 0),
            rating_down=uv2.get("down", 0),
            vip_perk=details1,
            shared_interests=shared_interests,
            starter_quote=starter_blockquote,
        )
        text2 = PARTNER_FOUND_TEMPLATE.format(
            rating_up=uv1.get("up", 0),
            rating_down=uv1.get("down", 0),
            vip_perk=details2,
            shared_interests=shared_interests,
            starter_quote=starter_blockquote,
        )

    msg1 = await safe_tele_func_call(
        context.bot.send_message, chat_id=user1,
        text=text1,
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
        text=text2,
        parse_mode="HTML",
        reply_markup=IN_CHAT_KEYBOARD,
    )
    if msg2 is None:
        # User2 blocked the bot
        logger.info(f"User {user2} blocked bot during match creation. Aborting session.")
        await end_chat_session(context, user2, reason="transport_disconnect", notify_initiator=False, notify_partner=True)
        return False

    # Record chat streak progress upon successful matching (both users searched and paired)
    try:
        from streaks import record_chat_interaction
        bot_inst = getattr(context, "bot", None)
        record_chat_interaction(user1, bot=bot_inst)
        record_chat_interaction(user2, bot=bot_inst)
    except Exception as e:
        logger.debug(f"Streak record on match error: {e}")

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

        session_start = init.session_start_times.pop(user_id, None)
        if partner:
            init.session_start_times.pop(partner, None)

        if session_start:
            session_dur = max(0.0, time.time() - session_start)
            if user_id in init.user_details:
                init.user_details[user_id]["total_chat_duration"] = init.user_details[user_id].get("total_chat_duration", 0.0) + session_dur
            if partner and partner in init.user_details:
                init.user_details[partner]["total_chat_duration"] = init.user_details[partner].get("total_chat_duration", 0.0) + session_dur

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

    try:
        from commands.call import active_voice_calls
        if session_id:
            active_voice_calls.pop(session_id, None)
    except Exception:
        pass

    # Persist session termination in PostgreSQL
    if session_id:
        try:
            await end_chat_session_db(session_id, reason)
        except Exception as e:
            logger.error(f"Error persisting session end for {session_id}: {e}")

    # Dispatch notifications with end-of-chat options (Friends & Transcript & Undo)
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from saveNload import are_friends_db

    # Record skip or stop for 60s accidental disconnect undo
    if partner and reason in ("user_stopped", "skipped"):
        init.recent_skips[user_id] = (partner, time.time())

    already_friends = await are_friends_db(user_id, partner) if partner else False
    has_transcript = bool(session_id and session_id in init.session_messages and len(init.session_messages[session_id]) >= 1)


    def _build_end_keyboard(target_pid, is_initiator=False):
        btns = []
        if is_initiator and target_pid and reason in ("user_stopped", "skipped"):
            btn_label = "↩️ Undo Stop (60s)" if reason == "user_stopped" else "↩️ Undo Skip (60s)"
            btns.append([InlineKeyboardButton(btn_label, callback_data=f"undoskip|{target_pid}")])
        if target_pid and not already_friends:
            btns.append([InlineKeyboardButton("⭐ Add to Anonymous Friends", callback_data=f"friendreq_end|{target_pid}")])
        if has_transcript:
            btns.append([InlineKeyboardButton("📥 Save Conversation Transcript", callback_data=f"export_chat|{session_id}")])
        return InlineKeyboardMarkup(btns) if btns else None

    if partner and notify_partner:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=partner,
            text=PARTNER_LEFT_CHAT_TEXT,
            parse_mode="HTML",
            reply_markup=IDLE_KEYBOARD,
        )
        kb_p = _build_end_keyboard(user_id, is_initiator=False)
        if kb_p:
            await safe_tele_func_call(
                context.bot.send_message,
                chat_id=partner,
                text="💬 <b>Chat Options:</b>",
                parse_mode="HTML",
                reply_markup=kb_p,
            )

    if notify_initiator:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user_id,
            text=CHAT_ENDED_TEXT,
            parse_mode="HTML",
            reply_markup=IDLE_KEYBOARD,
        )
        kb_u = _build_end_keyboard(partner, is_initiator=True)
        if kb_u:
            await safe_tele_func_call(
                context.bot.send_message,
                chat_id=user_id,
                text="💬 <b>Chat Options:</b>",
                parse_mode="HTML",
                reply_markup=kb_u,
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
