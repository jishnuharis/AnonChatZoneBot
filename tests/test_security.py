"""
Automated Security, Rate Limiting & Subscription Stacking Tests.
"""

import pytest
import time
from html import escape as esc

import init
from security import check_rate_limit, format_duration, MSG_RATE_LIMIT
from subscription import grant_subscription, is_subscribed, daily_credit_limit


@pytest.fixture(autouse=True)
def reset_globals():
    init.user_details.clear()
    init.dirty_users.clear()


def test_rate_limiting_anti_spam():
    user_id = 12345
    # Send MSG_RATE_LIMIT messages rapidly -> all pass
    for _ in range(MSG_RATE_LIMIT):
        assert check_rate_limit(user_id) is True

    # Next immediate message within 1.0s window must be throttled!
    assert check_rate_limit(user_id) is False


def test_html_input_escaping():
    malicious = "<script>alert('xss')</script> & <b>test</b>"
    escaped = esc(malicious)
    assert "<script>" not in escaped
    assert "&lt;script&gt;" in escaped
    assert "&amp;" in escaped


def test_subscription_stacking_no_downgrade():
    """
    Guarantees that a user with an active Yearly plan does NOT get downgraded
    to Daily when purchasing/gifted a Daily plan.
    """
    user_id = 555
    init.user_details[user_id] = init._default_user()

    # 1. Grant Yearly plan (365 days, limit bonus 64)
    yearly_exp = grant_subscription(user_id, "yearly", source="purchase")
    assert is_subscribed(user_id) is True
    assert init.user_details[user_id]["subscription_tier"] == "yearly"
    assert daily_credit_limit(user_id) == 32 + 64

    # 2. Grant Daily plan (+1 day)
    new_exp = grant_subscription(user_id, "daily", source="purchase")
    assert new_exp > yearly_exp
    # Tier must remain YEARLY, not downgraded to Daily!
    assert init.user_details[user_id]["subscription_tier"] == "yearly"
    assert daily_credit_limit(user_id) == 32 + 64


def test_format_duration():
    assert format_duration(65) == "1m"
    assert format_duration(3665) == "1h 1m"
    assert format_duration(86400 + 3600 + 120) == "1d 1h 2m"
