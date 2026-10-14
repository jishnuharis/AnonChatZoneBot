import time
import logging

import init
from message import SUBSCRIPTION_STATUS_FREE_TEXT, SUBSCRIPTION_STATUS_VIP_TEXT

logger = logging.getLogger(__name__)

FREE_DAILY_CREDIT_LIMIT = 32
FREE_DAILY_CALL_LIMIT = 3

FREE_TIER_BADGE = "💬"
FREE_TIER_LABEL = "Free Member"

TIERS = {
    "daily": {
        "label": "Daily",
        "duration_days": 1,
        "limit_bonus": 16,
        "stars": 25,
        "direct_price": "₹20 / $0.24",
        "badge": "⚡",
        "bonus_points": 50,
        "priority": 1,
    },
    "weekly": {
        "label": "Weekly",
        "duration_days": 7,
        "limit_bonus": 32,
        "stars": 125,
        "direct_price": "₹100 / $1.20",
        "badge": "✨",
        "bonus_points": 200,
        "priority": 2,
    },
    "monthly": {
        "label": "Monthly",
        "duration_days": 30,
        "limit_bonus": 48,
        "stars": 450,
        "direct_price": "₹300 / $3.60",
        "badge": "🌙",
        "bonus_points": 800,
        "priority": 3,
    },
    "yearly": {
        "label": "Yearly",
        "duration_days": 365,
        "limit_bonus": 64,
        "stars": 4500,
        "direct_price": "₹2,400 / $28.80",
        "badge": "👑",
        "bonus_points": 3500,
        "priority": 4,
    },
}

TIER_ORDER = ["daily", "weekly", "monthly", "yearly"]


def _details(user_id: int) -> dict:
    if user_id not in init.user_details:
        init.user_details[user_id] = init._default_user()
    return init.user_details[user_id]


def is_subscribed(user_id: int) -> bool:
    expires = init.user_details.get(user_id, {}).get("subscription_expires")
    return bool(expires) and expires > time.time()


def active_tier(user_id: int):
    if not is_subscribed(user_id):
        return None
    tier_key = init.user_details.get(user_id, {}).get("subscription_tier")
    return TIERS.get(tier_key)


def get_tier_badge(user_id: int) -> str:
    """Returns the badge emoji for the user's tier (💬 for free, ⚡, ✨, 🌙, 👑 for VIP)."""
    tier = active_tier(user_id)
    if not tier:
        return FREE_TIER_BADGE
    return tier.get("badge", "⭐")


def get_tier_display_name(user_id: int) -> str:
    """Returns formatted badge and label, e.g. '🌙 Monthly VIP' or '💬 Free Member'."""
    tier = active_tier(user_id)
    if not tier:
        return f"{FREE_TIER_BADGE} {FREE_TIER_LABEL}"
    return f"{tier.get('badge', '⭐')} {tier['label']} VIP"


def has_tier(user_id: int, min_tier_key: str) -> bool:
    """
    Returns True if user has an active subscription at or above min_tier_key.
    Example: has_tier(uid, 'weekly') returns True for weekly, monthly, and yearly.
    """
    tier = active_tier(user_id)
    if not tier:
        return False
    min_priority = TIERS.get(min_tier_key, {}).get("priority", 99)
    return tier.get("priority", 0) >= min_priority


def daily_credit_limit(user_id: int) -> int:
    tier = active_tier(user_id)
    if not tier:
        return FREE_DAILY_CREDIT_LIMIT
    return FREE_DAILY_CREDIT_LIMIT + tier["limit_bonus"]


def get_friend_limit(user_id: int) -> int:
    """Returns the maximum number of friends allowed: 16 base for free, +16 per tier level."""
    tier = active_tier(user_id)
    if not tier:
        return 16
    return 16 + (tier.get("priority", 1) * 16)


def daily_credits_used(user_id: int) -> int:
    details = _details(user_id)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if details.get("daily_credits_reset_day") != today:
        details["daily_credits_reset_day"] = today
        details["daily_credits_used"] = 0
        init.dirty_users.add(user_id)
    return details.get("daily_credits_used", 0)


def consume_daily_credit(user_id: int):
    daily_credits_used(user_id)
    details = _details(user_id)
    details["daily_credits_used"] = details.get("daily_credits_used", 0) + 1
    init.dirty_users.add(user_id)


def has_daily_credit(user_id: int) -> bool:
    return daily_credits_used(user_id) < daily_credit_limit(user_id)


def daily_calls_used(user_id: int) -> int:
    details = _details(user_id)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if details.get("daily_calls_reset_day") != today:
        details["daily_calls_reset_day"] = today
        details["daily_calls_used"] = 0
        init.dirty_users.add(user_id)
    return details.get("daily_calls_used", 0)


def consume_daily_call(user_id: int):
    """Consumes 1 daily voice call for free-tier users. Paid users are unlimited."""
    if is_subscribed(user_id):
        return
    daily_calls_used(user_id)
    details = _details(user_id)
    details["daily_calls_used"] = details.get("daily_calls_used", 0) + 1
    init.dirty_users.add(user_id)


def can_make_call(user_id: int) -> tuple[bool, int, int]:
    """
    Checks if user is allowed to initiate a voice call.
    Returns (allowed, used, limit) where limit=-1 denotes unlimited.
    """
    if is_subscribed(user_id):
        return (True, daily_calls_used(user_id), -1)
    used = daily_calls_used(user_id)
    return (used < FREE_DAILY_CALL_LIMIT, used, FREE_DAILY_CALL_LIMIT)


def grant_subscription(user_id: int, tier_key: str, source: str = "purchase") -> float:
    """
    Grants or extends a subscription.
    Guarantees no accidental tier downgrading when adding shorter plans to a higher plan.
    """
    if tier_key not in TIERS:
        raise ValueError(f"Unknown subscription tier: {tier_key}")

    new_tier_info = TIERS[tier_key]
    details = _details(user_id)

    now = time.time()
    current_expiry = details.get("subscription_expires") or 0
    current_tier_key = details.get("subscription_tier")

    base = current_expiry if current_expiry > now else now
    new_expiry = base + new_tier_info["duration_days"] * 86400

    details["subscription_expires"] = new_expiry

    # Prevent tier downgrade: keep higher priority tier if currently active
    if current_tier_key in TIERS and current_expiry > now:
        current_priority = TIERS[current_tier_key].get("priority", 0)
        new_priority = new_tier_info.get("priority", 0)
        if new_priority >= current_priority:
            details["subscription_tier"] = tier_key
        # else retain current_tier_key
    else:
        details["subscription_tier"] = tier_key

    details["points"] = details.get("points", 0) + new_tier_info["bonus_points"]
    init.dirty_users.add(user_id)
    return new_expiry


def grant_vip_days(user_id: int, days: int, tier_key: str = "daily", source: str = "streak_reward") -> float:
    """
    Grants or extends VIP access by a specific number of days.
    Guarantees no accidental tier downgrading when adding days.
    """
    details = _details(user_id)
    now = time.time()
    current_expiry = details.get("subscription_expires") or 0
    current_tier_key = details.get("subscription_tier")

    base = current_expiry if current_expiry > now else now
    new_expiry = base + days * 86400

    details["subscription_expires"] = new_expiry

    if current_tier_key in TIERS and current_expiry > now:
        current_priority = TIERS[current_tier_key].get("priority", 0)
        new_priority = TIERS.get(tier_key, {}).get("priority", 1)
        if new_priority >= current_priority:
            details["subscription_tier"] = tier_key
    else:
        details["subscription_tier"] = tier_key

    init.dirty_users.add(user_id)
    return new_expiry


def grant_vip_hours(user_id: int, hours: float = 1.0, tier_key: str = "daily", source: str = "rush_hour") -> float:
    """
    Grants or extends VIP access by a specific number of hours.
    Guarantees no accidental tier downgrading when adding hours.
    """
    details = _details(user_id)
    now = time.time()
    current_expiry = details.get("subscription_expires") or 0
    current_tier_key = details.get("subscription_tier")

    base = current_expiry if current_expiry > now else now
    new_expiry = base + hours * 3600

    details["subscription_expires"] = new_expiry

    if current_tier_key in TIERS and current_expiry > now:
        current_priority = TIERS[current_tier_key].get("priority", 0)
        new_priority = TIERS.get(tier_key, {}).get("priority", 1)
        if new_priority >= current_priority:
            details["subscription_tier"] = tier_key
    else:
        details["subscription_tier"] = tier_key

    init.dirty_users.add(user_id)
    return new_expiry


def status_text(user_id: int) -> str:
    tier = active_tier(user_id)
    if not tier:
        used_calls = daily_calls_used(user_id)
        rem_calls = max(0, FREE_DAILY_CALL_LIMIT - used_calls)
        return SUBSCRIPTION_STATUS_FREE_TEXT.format(
            badge=FREE_TIER_BADGE,
            label=FREE_TIER_LABEL,
            rem_calls=rem_calls,
            call_limit=FREE_DAILY_CALL_LIMIT,
            credit_limit=FREE_DAILY_CREDIT_LIMIT,
        )
    expires = init.user_details[user_id]["subscription_expires"]
    rem_secs = max(0, (expires - time.time()))
    if rem_secs < 86400:
        rem_hrs = rem_secs / 3600
        time_left_str = f"{rem_hrs:.1f} hours left" if rem_hrs >= 1 else f"{max(1, int(rem_secs // 60))} minutes left"
    else:
        remaining_days = rem_secs / 86400
        time_left_str = f"{remaining_days:.1f} days left"

    return SUBSCRIPTION_STATUS_VIP_TEXT.format(
        badge=tier.get("badge", "⭐"),
        label=tier["label"],
        time_left_str=time_left_str,
        credit_limit=daily_credit_limit(user_id),
    )

