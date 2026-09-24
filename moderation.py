import time
import logging
from typing import Optional, Tuple
from datetime import datetime, timezone

import init
from saveNload import record_user_report, apply_user_restriction_db, clear_user_restriction_db, decay_severity_scores_sql

logger = logging.getLogger(__name__)

REPORT_REASONS = {
    "spam": ("Spam / Ads", 1),
    "rude": ("Rude / Toxic behaviour", 2),
    "nsfw": ("Unwanted NSFW", 4),
    "harass": ("Harassment / Threats", 5),
    "scam": ("Scam / Phishing", 6),
    "leak": ("Leaked my private media", 7),
    "minor": ("Underage concern", 10),
}

SEVERITY_SCORE_THRESHOLDS = [
    (200, 10), (181, 9), (162, 8), (143, 7), (124, 6), (105, 5), (86, 4), (67, 3), (48, 2), (32, 1),
]

SEVERITY_DURATIONS = {
    0: 0,
    1: 5 * 60,
    2: 30 * 60,
    3: 2 * 3600,
    4: 6 * 3600,
    5: 12 * 3600,
    6: 24 * 3600,
    7: 3 * 24 * 3600,
    8: 7 * 24 * 3600,
    9: 30 * 24 * 3600,
    10: 3650 * 24 * 3600,
}

SEVERITY_DECAY_PER_DAY = 1


def is_admin(user_id: int) -> bool:
    try:
        if init.OWNER and int(user_id) == int(init.OWNER):
            return True
    except (TypeError, ValueError):
        pass
    return user_id in init.ADMIN_IDS


def is_user_restricted(user_id: int) -> Tuple[bool, Optional[str], Optional[float]]:
    """
    Checks if a user is currently restricted or banned.
    Returns (is_restricted, reason, seconds_remaining).
    """
    if is_admin(user_id):
        return False, None, None

    details = init.user_details.get(user_id)
    if not details:
        return False, None, None

    restricted_until = details.get("restricted_until")
    if restricted_until:
        now = time.time()
        if now < restricted_until:
            reason = details.get("restriction_reason") or "Violation of bot rules"
            return True, reason, restricted_until - now
        else:
            # Expired restriction
            details["restricted_until"] = None
            details["restriction_reason"] = None
            init.dirty_users.add(user_id)
    return False, None, None


def severity_for_score(score: int) -> int:
    for threshold, severity in SEVERITY_SCORE_THRESHOLDS:
        if score >= threshold:
            return severity
    return 0


def _ensure_user(user_id: int):
    if user_id not in init.user_details:
        init.user_details[user_id] = init._default_user()
    return init.user_details[user_id]


async def apply_restriction(user_id: int, severity: int, reason: str, duration_override: int = None, context=None) -> Optional[float]:
    """
    Applies restriction or ban.
    ENFORCEMENT (Requirement 2 & 3):
    1. Removes user immediately from waiting queue.
    2. Immediately severs any active chat session.
    3. Persists to DB.
    """
    if is_admin(user_id):
        return None

    severity = max(0, min(10, severity))
    duration = duration_override if duration_override is not None else SEVERITY_DURATIONS.get(severity, 0)

    details = _ensure_user(user_id)

    if duration <= 0:
        return details.get("restricted_until")

    until = time.time() + duration
    current = details.get("restricted_until") or 0
    if until > current:
        details["restricted_until"] = until
        details["restriction_reason"] = reason

    init.dirty_users.add(user_id)

    # 1. Enforce eviction from waiting queue immediately!
    async with init.queue_lock:
        if user_id in init.waiting_users:
            init.waiting_users.remove(user_id)
            init.wait_started.pop(user_id, None)
            logger.info(f"Evicted restricted user {user_id} from matchmaking queue.")

    # 2. Enforce immediate severance of active chat session
    if user_id in init.active_pairs and context is not None:
        try:
            from session_manager import end_chat_session
            await end_chat_session(context, user_id, reason="banned", notify_initiator=True, notify_partner=True)
            logger.info(f"Severed active chat session for restricted user {user_id}.")
        except Exception as e:
            logger.error(f"Error ending chat session during restriction for user {user_id}: {e}")

    # 3. Persist to PostgreSQL
    try:
        until_dt = datetime.fromtimestamp(until, timezone.utc)
        await apply_user_restriction_db(user_id, until_dt, reason, is_banned=(severity >= 10))
    except Exception as e:
        logger.error(f"DB update failed during restriction of user {user_id}: {e}")

    return details["restricted_until"]


async def clear_restriction(user_id: int):
    """Lifts any restriction on the user in memory and database."""
    details = _ensure_user(user_id)
    details["restricted_until"] = None
    details["restriction_reason"] = None
    init.dirty_users.add(user_id)
    try:
        await clear_user_restriction_db(user_id)
    except Exception as e:
        logger.error(f"DB update failed during clear_restriction for user {user_id}: {e}")


async def file_report(reporter_id: int, target_id: int, reason_code: str, context=None) -> Tuple[int, int, Optional[int]]:
    if reason_code not in REPORT_REASONS:
        return 0, 0, None

    label, weight = REPORT_REASONS[reason_code]
    details = _ensure_user(target_id)

    before_score = details.get("severity_score", 0)
    before_severity = severity_for_score(before_score)

    details["severity_score"] = before_score + weight
    details["reports"] = details.get("reports", 0) + 1
    log = details.setdefault("report_log", [])
    log.append({
        "reporter": reporter_id,
        "reason": reason_code,
        "weight": weight,
        "timestamp": time.time(),
    })
    if len(log) > 50:
        del log[: len(log) - 50]

    after_score = details["severity_score"]
    after_severity = severity_for_score(after_score)

    init.dirty_users.add(target_id)

    # Record normalized report in database
    try:
        await record_user_report(reporter_id, target_id, reason_code, weight)
    except Exception as e:
        logger.error(f"Failed to record report in DB: {e}")

    triggered = None
    if after_severity > before_severity and not is_admin(target_id):
        await apply_restriction(target_id, after_severity, f"Multiple reports ({label})", context=context)
        triggered = after_severity

    return weight, after_score, triggered


async def decay_severity_scores():
    """
    Delegates severity decay to PostgreSQL in O(1) time.
    Also updates in-memory cached scores.
    """
    try:
        decayed_count = await decay_severity_scores_sql(decay_rate=SEVERITY_DECAY_PER_DAY)
        if decayed_count > 0:
            logger.info(f"Decayed severity scores for {decayed_count} users in DB.")
    except Exception as e:
        logger.error(f"Error during severity decay: {e}")

    # Update in-memory cached entries safely
    now = time.time()
    for user_id in list(init.user_details.keys()):
        details = init.user_details.get(user_id)
        if not details:
            continue
        last_decay = details.get("last_severity_decay") or now
        days_passed = (now - last_decay) / 86400
        if days_passed >= 1:
            score = details.get("severity_score", 0)
            if score > 0:
                details["severity_score"] = max(0, score - int(days_passed) * SEVERITY_DECAY_PER_DAY)
            details["last_severity_decay"] = now
