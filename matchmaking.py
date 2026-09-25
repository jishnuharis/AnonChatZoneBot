"""
Matchmaking and Queue Engine for AnonChatZoneBot.

Guarantees:
1. Concurrency-safe queue operations protected by `init.queue_lock`.
2. Multi-layered ban & block enforcement:
   - Banned and restricted users can NEVER enter the queue.
   - Banned and restricted users are purged from the queue.
   - Users who blocked each other can NEVER be matched.
3. Rematch suppression: avoids pairing with recent partners when possible.
4. Preference-based matching with fallback FIFO sweep.
5. Integration with centralized session_manager.
"""

import time
import logging
from typing import Optional, Tuple
from telegram.ext import ContextTypes

import init
from moderation import is_user_restricted
from saveNload import is_blocked_pairwise
from session_manager import start_chat_session, is_in_chat
from subscription import is_subscribed

logger = logging.getLogger(__name__)

MATCH_GRACE_PERIOD = 15


def _prefs(user_id: int) -> int:
    return init.user_details.get(user_id, {}).get("preferences", 0)


def _overlap_score(a: int, b: int) -> int:
    return bin(_prefs(a) & _prefs(b)).count("1")


def _matches_filters(user_id: int, other_id: int) -> bool:
    """
    Validates whether 'other_id' satisfies 'user_id's paid preferences,
    and whether 'user_id' satisfies 'other_id's paid preferences.
    """
    u_details = init.user_details.get(user_id, {})
    o_details = init.user_details.get(other_id, {})

    # 1. If user_id has an active subscription, enforce user_id's preferences
    if is_subscribed(user_id):
        pref_g = u_details.get("pref_gender", "ANY")
        if pref_g in ("M", "F"):
            if o_details.get("gender") != pref_g:
                return False

        pref_c = u_details.get("pref_country", "ANY")
        if pref_c == "SAME":
            u_country = u_details.get("country")
            if not u_country or o_details.get("country") != u_country:
                return False
        elif pref_c and pref_c != "ANY":
            if o_details.get("country") != pref_c:
                return False

    # 2. If other_id has an active subscription, enforce other_id's preferences
    if is_subscribed(other_id):
        o_pref_g = o_details.get("pref_gender", "ANY")
        if o_pref_g in ("M", "F"):
            if u_details.get("gender") != o_pref_g:
                return False

        o_pref_c = o_details.get("pref_country", "ANY")
        if o_pref_c == "SAME":
            o_country = o_details.get("country")
            if not o_country or u_details.get("country") != o_country:
                return False
        elif o_pref_c and o_pref_c != "ANY":
            if u_details.get("country") != o_pref_c:
                return False

    return True


async def _is_eligible_candidate(user_id: int, other_id: int) -> bool:
    """Validates that candidate is not banned, blocked, in chat, or self, and satisfies filters."""
    if user_id == other_id:
        return False

    if is_in_chat(other_id):
        return False

    # Check ban/restriction
    restricted, _, _ = is_user_restricted(other_id)
    if restricted:
        return False

    # Check mutual block
    if await is_blocked_pairwise(user_id, other_id):
        return False

    # Check subscriber gender and country preferences
    if not _matches_filters(user_id, other_id):
        return False

    return True


def _candidate_score(user_id: int, other_id: int) -> int:
    """
    Calculates match suitability score between user_id and other_id.
    - Base: interest tag overlap count (0..10).
    - Paid subscriber priority boost (+100 if either user is subscribed).
    """
    score = _overlap_score(user_id, other_id)
    if is_subscribed(user_id) or is_subscribed(other_id):
        score += 100
    return score


async def _find_best_partner(user_id: int) -> Tuple[Optional[int], int]:
    """Finds best matching partner in queue respecting preferences, blocks, and rematches."""
    best_id, best_score = None, -1
    recent = set(init.recent_partners.get(user_id, []))

    eligible_candidates = []
    for other in list(init.waiting_users):
        if await _is_eligible_candidate(user_id, other):
            eligible_candidates.append(other)

    if not eligible_candidates:
        return None, -1

    # First pass: prefer candidates that are NOT recent partners and have positive overlap
    for other in eligible_candidates:
        if other in recent and len(eligible_candidates) > 1:
            continue
        score = _candidate_score(user_id, other)
        if score > best_score:
            best_score = score
            best_id = other

    # Fallback to any eligible candidate if all are recent partners
    if best_id is None:
        for other in eligible_candidates:
            score = _candidate_score(user_id, other)
            if score > best_score:
                best_score = score
                best_id = other

    return best_id, best_score


async def dequeue_user(user_id: int) -> bool:
    """Removes a user from the matchmaking queue and waiting timers."""
    async with init.queue_lock:
        removed = False
        if user_id in init.waiting_users:
            init.waiting_users.remove(user_id)
            removed = True
        init.wait_started.pop(user_id, None)
        return removed


async def enqueue_and_match(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """
    Enqueues user and attempts an immediate interest-based match.
    Enforces ban/block checks at queue entrance and match creation.
    """
    # Layer 1: Entrance Ban Check
    restricted, reason, remaining = is_user_restricted(user_id)
    if restricted:
        logger.warning(f"Banned user {user_id} attempted to enter queue. Rejected.")
        return False

    if is_in_chat(user_id):
        return False

    async with init.queue_lock:
        if user_id not in init.waiting_users:
            init.waiting_users.append(user_id)
            init.wait_started[user_id] = time.time()

        if len(init.waiting_users) < 2:
            return False

        partner, score = await _find_best_partner(user_id)
        now_ts = time.time()
        partner_waited = (now_ts - init.wait_started.get(partner, now_ts)) >= MATCH_GRACE_PERIOD if partner else False

        # Match immediately if positive interest overlap (score > 0),
        # or if subscriber match filter is satisfied, or if partner has waited past grace period
        if partner is not None and (score > 0 or is_subscribed(user_id) or is_subscribed(partner) or partner_waited):
            if user_id in init.waiting_users:
                init.waiting_users.remove(user_id)
            if partner in init.waiting_users:
                init.waiting_users.remove(partner)
            init.wait_started.pop(user_id, None)
            init.wait_started.pop(partner, None)

            # Layer 2 & 3: Match Creation
            return await start_chat_session(context, user_id, partner)

    return False


async def queue_sweep(context: ContextTypes.DEFAULT_TYPE):
    """
    Periodic FIFO sweep for users waiting longer than MATCH_GRACE_PERIOD.
    Purges any stale, banned, or blocked entries from the queue.
    """
    now = time.time()

    async with init.queue_lock:
        # Purge any banned, restricted, or already chatting users from queue
        stale = []
        for uid in list(init.waiting_users):
            restr, _, _ = is_user_restricted(uid)
            if restr or is_in_chat(uid):
                stale.append(uid)

        for uid in stale:
            if uid in init.waiting_users:
                init.waiting_users.remove(uid)
            init.wait_started.pop(uid, None)
            logger.info(f"Purged invalid/banned user {uid} from queue during sweep.")

        while len(init.waiting_users) >= 2:
            # Find eligible users waiting longer than MATCH_GRACE_PERIOD
            eligible_oldest = [
                u for u in init.waiting_users 
                if (now - init.wait_started.get(u, now)) >= MATCH_GRACE_PERIOD
            ]
            if not eligible_oldest:
                break

            oldest = min(eligible_oldest, key=lambda u: init.wait_started.get(u, now))
            partner, _ = await _find_best_partner(oldest)

            if partner is None:
                # No eligible partner in queue right now (e.g. mutual blocks)
                break

            if oldest in init.waiting_users:
                init.waiting_users.remove(oldest)
            if partner in init.waiting_users:
                init.waiting_users.remove(partner)
            init.wait_started.pop(oldest, None)
            init.wait_started.pop(partner, None)

            await start_chat_session(context, oldest, partner)
