import time
import logging

import init

logger = logging.getLogger(__name__)

FREE_DAILY_CREDIT_LIMIT = 32

TIERS = {
    "daily": {
        "label": "Daily",
        "duration_days": 1,
        "limit_bonus": 16,
        "stars": 20,
        "bonus_points": 40,
        "priority": 1,
    },
    "weekly": {
        "label": "Weekly",
        "duration_days": 7,
        "limit_bonus": 32,
        "stars": 70,
        "bonus_points": 150,
        "priority": 2,
    },
    "monthly": {
        "label": "Monthly",
        "duration_days": 30,
        "limit_bonus": 48,
        "stars": 150,
        "bonus_points": 400,
        "priority": 3,
    },
    "yearly": {
        "label": "Yearly",
        "duration_days": 365,
        "limit_bonus": 64,
        "stars": 999,
        "bonus_points": 3000,
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


def daily_credit_limit(user_id: int) -> int:
    tier = active_tier(user_id)
    if not tier:
        return FREE_DAILY_CREDIT_LIMIT
    return FREE_DAILY_CREDIT_LIMIT + tier["limit_bonus"]


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


def status_text(user_id: int) -> str:
    tier = active_tier(user_id)
    if not tier:
        return "❌ <i>No active subscription. Use</i> /subscribe <i>to unlock perks.</i>"
    expires = init.user_details[user_id]["subscription_expires"]
    remaining_days = max(0, (expires - time.time()) / 86400)
    return (
        f"✅ <b>{tier['label']}</b> <i>plan active</i> — "
        f"<i>{remaining_days:.1f} days left</i>\n"
        f"<i>Daily credit limit:</i> {daily_credit_limit(user_id)} "
        f"<i>(/next skips; media sends are free & unlimited on your plan)</i>"
    )
