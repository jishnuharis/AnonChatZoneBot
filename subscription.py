import time

import init

# ---------------------------------------------------------------------------
# Subscription tiers
# ---------------------------------------------------------------------------
# duration_days   : how long a purchase/grant of this tier lasts
# limit_bonus     : added on top of FREE_DAILY_CREDIT_LIMIT for the daily
#                   credit pool - shared by /next skips (all users) and
#                   photo/video/voice/video note sends (free-tier users only;
#                   subscribers send all media free of charge, see media_privacy.py/relay.py)
# stars           : price in Telegram Stars (XTR) - see pricing note below
# bonus_points    : one-off in-bot points awarded when this tier is bought/granted
#
# limit_bonus climbs by +16 per tier (daily=+16, weekly=+32, monthly=+48,
# yearly=+64) as requested. Stars pricing is a *starting point*, not a
# guarantee of profitability - see the note at the bottom of this file.
FREE_DAILY_CREDIT_LIMIT = 32

TIERS = {
    "daily": {
        "label": "Daily",
        "duration_days": 1,
        "limit_bonus": 16,
        "stars": 20,
        "bonus_points": 40,
    },
    "weekly": {
        "label": "Weekly",
        "duration_days": 7,
        "limit_bonus": 32,
        "stars": 70,
        "bonus_points": 150,
    },
    "monthly": {
        "label": "Monthly",
        "duration_days": 30,
        "limit_bonus": 48,
        "stars": 150,
        "bonus_points": 400,
    },
    "yearly": {
        "label": "Yearly",
        "duration_days": 365,
        "limit_bonus": 64,
        "stars": 999,
        "bonus_points": 3000,
    },
}

TIER_ORDER = ["daily", "weekly", "monthly", "yearly"]


def _details(user_id: int) -> dict:
    if user_id not in init.user_details:
        from init import _default_user
        init.user_details[user_id] = _default_user()
    return init.user_details[user_id]


def is_subscribed(user_id: int) -> bool:
    """Single source of truth for subscription status. A user counts as
    subscribed if subscription_expires is set and still in the future -
    nothing else (tier, points, etc.) should be checked to decide this."""
    expires = init.user_details.get(user_id, {}).get("subscription_expires")
    return bool(expires) and expires > time.time()


def active_tier(user_id: int):
    """Returns the tier dict for the user's active subscription, or None."""
    if not is_subscribed(user_id):
        return None
    tier_key = init.user_details.get(user_id, {}).get("subscription_tier")
    return TIERS.get(tier_key)


def daily_credit_limit(user_id: int) -> int:
    """Max daily credits (shared by /next skips and photo/video/voice/video note
    sends for free-tier users). Subscribers effectively never run out since
    they send all media free & unlimited and only /next still draws from this
    pool for them too - the tier's limit_bonus just gives paying users more headroom."""
    tier = active_tier(user_id)
    if not tier:
        return FREE_DAILY_CREDIT_LIMIT
    return FREE_DAILY_CREDIT_LIMIT + tier["limit_bonus"]


def daily_credits_used(user_id: int) -> int:
    """Returns how many daily credits this user has used today (from /next
    skips and, for free-tier users, photo/video/voice/video note sends),
    resetting the counter first if the stored day doesn't match today (UTC)."""
    details = _details(user_id)
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if details.get("next_used_day") != today:
        details["next_used_day"] = today
        details["next_used_today"] = 0
        init.dirty_users.add(user_id)
    return details.get("next_used_today", 0)


def consume_daily_credit(user_id: int):
    daily_credits_used(user_id)  # ensures the day rollover happened first
    details = _details(user_id)
    details["next_used_today"] = details.get("next_used_today", 0) + 1
    init.dirty_users.add(user_id)


def has_daily_credit(user_id: int) -> bool:
    return daily_credits_used(user_id) < daily_credit_limit(user_id)


def grant_subscription(user_id: int, tier_key: str, source: str = "purchase") -> float:
    """Activates or extends a subscription for user_id and awards the tier's
    bonus points. Extends from the current expiry if already subscribed
    (rather than overwriting it), so stacking purchases/grants doesn't waste
    remaining time. Returns the new expiry timestamp.

    `source` is just for bookkeeping/logging (e.g. "purchase" vs "admin_grant")
    and doesn't change the behaviour - an admin grant gives the same perks and
    points a purchase would, so gifted time is worth the same as paid time.
    """
    if tier_key not in TIERS:
        raise ValueError(f"Unknown subscription tier: {tier_key}")

    tier = TIERS[tier_key]
    details = _details(user_id)

    now = time.time()
    current_expiry = details.get("subscription_expires") or 0
    base = current_expiry if current_expiry > now else now
    new_expiry = base + tier["duration_days"] * 86400

    details["subscription_expires"] = new_expiry
    details["subscription_tier"] = tier_key
    details["points"] = details.get("points", 0) + tier["bonus_points"]

    init.dirty_users.add(user_id)
    return new_expiry


def status_text(user_id: int) -> str:
    """Short HTML-safe status line for /profile and /subscribe."""
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


# ---------------------------------------------------------------------------
# Pricing note
# ---------------------------------------------------------------------------
# Telegram pays out roughly $0.013 per Star earned (creators withdraw via
# Fragment; buyers pay somewhat more, ~$0.02/Star in-app due to Apple/Google's
# cut). At the prices above, that's roughly:
#   daily    20 stars ~ $0.40 buyer-side / $0.40/day
#   weekly   70 stars ~ $1.40 buyer-side / $0.20/day  (discount vs 7x daily)
#   monthly 150 stars ~ $3.00 buyer-side / $0.10/day  (bigger discount)
#   yearly  999 stars ~ $20.00 buyer-side / $0.055/day (steepest discount -
#                        ~45% off what 12 back-to-back monthly plans would cost)
# This is a starting point to reflect "more perk value + longer commitment =
# better per-day price", not a validated price point - test and adjust based
# on actual conversion once you have real usage data.
