import time

import init

# ---------------------------------------------------------------------------
# Report reasons -> how many severity points they add
# ---------------------------------------------------------------------------
# code: (label shown to the user, weight added to the target's severity_score)
REPORT_REASONS = {
    "spam": ("Spam / Ads", 1),
    "rude": ("Rude / Toxic behaviour", 2),
    "nsfw": ("Unwanted NSFW", 4),
    "harass": ("Harassment / Threats", 5),
    "scam": ("Scam / Phishing", 6),
    "leak": ("Leaked my private media", 7),
    "minor": ("Underage concern", 10),
}

# Cumulative severity_score -> the ban severity (0-10) it should trigger.
# Scaled deliberately high (top tier sits at 200) so a handful of reports -
# including a single "underage concern" flag - can't auto-restrict someone on
# their own. It takes a real, sustained pattern of reports to trip this.
SEVERITY_SCORE_THRESHOLDS = [
    (200, 10), (181, 9), (162, 8), (143, 7), (124, 6), (105, 5), (86, 4), (67, 3), (48, 2), (32, 1),
]

# Ban severity (0-10) -> restriction duration in seconds
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
    10: 3650 * 24 * 3600,  # effectively permanent, an admin can still /unban
}

# severity_score points shaved off per day of good behaviour so old minor
# reports don't follow someone around forever
SEVERITY_DECAY_PER_DAY = 1


def is_admin(user_id: int) -> bool:
    try:
        if init.OWNER and int(user_id) == int(init.OWNER):
            return True
    except (TypeError, ValueError):
        pass
    return user_id in init.ADMIN_IDS


def severity_for_score(score: int) -> int:
    for threshold, severity in SEVERITY_SCORE_THRESHOLDS:
        if score >= threshold:
            return severity
    return 0


def _ensure_user(user_id: int):
    if user_id not in init.user_details:
        from init import _default_user
        init.user_details[user_id] = _default_user()
    return init.user_details[user_id]


def apply_restriction(user_id: int, severity: int, reason: str, duration_override: int = None) -> float:
    """Restricts a user. Only extends the restriction if it's longer than whatever's active.
    Admins (including the owner) can never end up restricted this way - manual or automatic -
    so a wave of reports (or a fat-fingered /ban) can never lock an admin out of their own bot."""
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
    return details["restricted_until"]


def clear_restriction(user_id: int):
    details = _ensure_user(user_id)
    details["restricted_until"] = None
    details["restriction_reason"] = None
    init.dirty_users.add(user_id)


def file_report(reporter_id: int, target_id: int, reason_code: str):
    """Logs a report against target_id and auto-restricts them if their score crosses a new tier.
    Returns (weight_added, new_score, new_severity_or_None)."""
    if reason_code not in REPORT_REASONS:
        return 0, 0, None

    label, weight = REPORT_REASONS[reason_code]
    details = _ensure_user(target_id)

    before_score = details.get("severity_score", 0)
    before_severity = severity_for_score(before_score)

    details["severity_score"] = before_score + weight
    log = details.setdefault("report_log", [])
    log.append({
        "reporter": reporter_id,
        "reason": reason_code,
        "weight": weight,
        "timestamp": time.time(),
    })
    # Keep the log from growing forever
    if len(log) > 50:
        del log[: len(log) - 50]

    after_score = details["severity_score"]
    after_severity = severity_for_score(after_score)

    init.dirty_users.add(target_id)

    triggered = None
    if after_severity > before_severity and not is_admin(target_id):
        apply_restriction(target_id, after_severity, f"Multiple reports ({label})")
        triggered = after_severity

    return weight, after_score, triggered


def decay_severity_scores():
    """Slowly forgives old severity points so a couple of stale minor reports don't
    keep someone permanently on thin ice. Meant to run on a daily job."""
    now = time.time()
    for user_id, details in init.user_details.items():
        last_decay = details.get("last_severity_decay") or now
        days_passed = (now - last_decay) / 86400
        if days_passed < 1:
            continue
        score = details.get("severity_score", 0)
        if score > 0:
            reduction = int(days_passed) * SEVERITY_DECAY_PER_DAY
            details["severity_score"] = max(0, score - reduction)
            init.dirty_users.add(user_id)
        details["last_severity_decay"] = now
