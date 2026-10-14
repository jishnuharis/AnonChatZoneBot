import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import init
from init import _default_user
import subscription
from commands.leaderboard import (
    award_weekly_leaderboard_prizes,
    weekly_leaderboard_job,
    pre_weekly_leaderboard_update_job,
    weekly_reward_admin_command,
    render_leaderboard_text,
    get_weekly_reset_countdown,
)


@pytest.fixture(autouse=True)
def clean_state():
    init.user_details.clear()
    init.dirty_users.clear()
    init.active_pairs.clear()
    init.waiting_users.clear()
    yield
    init.user_details.clear()
    init.dirty_users.clear()


@pytest.mark.asyncio
async def test_award_all_distinct_users(monkeypatch):
    """When top 3 users in streaks, karma, and games are all distinct, 9 unique users get 1 day VIP."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_add_db = AsyncMock()
    monkeypatch.setattr("saveNload.add_subscription_db", mock_add_db)

    # 3 streak users
    for i in range(1, 4):
        uid = 1000 + i
        init.user_details[uid] = {**_default_user(), "current_streak": i * 10, "longest_streak": i * 10}

    # 3 karma users
    for i in range(1, 4):
        uid = 2000 + i
        init.user_details[uid] = {**_default_user(), "votes": {"up": i * 20, "down": 0}}

    # 3 games users
    for i in range(1, 4):
        uid = 3000 + i
        init.user_details[uid] = {**_default_user(), "points": i * 500}

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await award_weekly_leaderboard_prizes(bot=mock_bot)

    assert result["awarded_count"] == 9
    assert len(result["awarded_users"]) == 9

    # Verify all 9 are subscribed with Daily tier
    for uid in result["awarded_users"]:
        assert subscription.is_subscribed(uid) is True
        assert subscription.has_tier(uid, "daily") is True
        user = init.user_details[uid]
        assert user.get("subscription_tier") == "daily"
        assert user.get("subscription_expires") > time.time()

    # Verify DB persistence called 9 times
    assert mock_add_db.call_count == 9
    # Verify bot sent DMs to all 9 winners
    assert mock_bot.send_message.call_count == 9


@pytest.mark.asyncio
async def test_award_single_user_in_all_categories(monkeypatch):
    """When a single user is in the top 3 across all 3 leaderboards, they get 1 day VIP awarded only once."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_add_db = AsyncMock()
    monkeypatch.setattr("saveNload.add_subscription_db", mock_add_db)

    super_user = 5555
    init.user_details[super_user] = {
        **_default_user(),
        "current_streak": 100,
        "longest_streak": 100,
        "votes": {"up": 200, "down": 0},
        "points": 5000,
    }

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await award_weekly_leaderboard_prizes(bot=mock_bot)

    assert result["awarded_count"] == 1
    assert result["awarded_users"] == [super_user]
    assert subscription.is_subscribed(super_user) is True

    # Check that they were granted 1 day (around 86400 seconds)
    exp = init.user_details[super_user]["subscription_expires"]
    assert abs(exp - (time.time() + 86400)) < 10

    # DB persistence called exactly once
    assert mock_add_db.call_count == 1
    assert mock_bot.send_message.call_count == 1

    # Verify message mentions multiple categories
    msg_call_kwargs = mock_bot.send_message.call_args[1]
    assert "Daily Chat Streaks" in msg_call_kwargs["text"]
    assert "Karma & Upvotes" in msg_call_kwargs["text"]
    assert "Mini-Games & Points" in msg_call_kwargs["text"]
    assert "1 Day of Free VIP Premium" in msg_call_kwargs["text"]


@pytest.mark.asyncio
async def test_award_with_overlap(monkeypatch):
    """Partial overlap: User A in streaks and games; User B in karma and streaks; User C in games."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_add_db = AsyncMock()
    monkeypatch.setattr("saveNload.add_subscription_db", mock_add_db)

    user_a = 6001
    user_b = 6002
    user_c = 6003

    init.user_details[user_a] = {
        **_default_user(),
        "current_streak": 50,
        "points": 3000,
    }
    init.user_details[user_b] = {
        **_default_user(),
        "current_streak": 40,
        "votes": {"up": 80, "down": 0},
    }
    init.user_details[user_c] = {
        **_default_user(),
        "points": 2000,
    }

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await award_weekly_leaderboard_prizes(bot=mock_bot)

    assert result["awarded_count"] == 3
    assert set(result["awarded_users"]) == {user_a, user_b, user_c}
    for uid in (user_a, user_b, user_c):
        assert subscription.is_subscribed(uid) is True

    assert mock_add_db.call_count == 3
    assert mock_bot.send_message.call_count == 3


@pytest.mark.asyncio
async def test_banned_users_and_zero_scores_excluded(monkeypatch):
    """Banned users and users with 0 score should not be awarded prizes."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_add_db = AsyncMock()
    monkeypatch.setattr("saveNload.add_subscription_db", mock_add_db)

    banned_uid = 7001
    init.user_details[banned_uid] = {
        **_default_user(),
        "current_streak": 99,
        "is_banned": True,
    }

    zero_uid = 7002
    init.user_details[zero_uid] = {
        **_default_user(),
        "current_streak": 0,
        "points": 0,
    }

    valid_uid = 7003
    init.user_details[valid_uid] = {
        **_default_user(),
        "current_streak": 5,
    }

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    result = await award_weekly_leaderboard_prizes(bot=mock_bot)

    assert result["awarded_count"] == 1
    assert result["awarded_users"] == [valid_uid]
    assert subscription.is_subscribed(valid_uid) is True
    assert not subscription.is_subscribed(banned_uid)
    assert not subscription.is_subscribed(zero_uid)


@pytest.mark.asyncio
async def test_extends_existing_vip_without_downgrading(monkeypatch):
    """If a winning user already has Monthly VIP, it extends by 1 day without downgrading tier."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_add_db = AsyncMock()
    monkeypatch.setattr("saveNload.add_subscription_db", mock_add_db)

    vip_uid = 8001
    init.user_details[vip_uid] = {
        **_default_user(),
        "current_streak": 20,
    }
    # Grant monthly subscription
    current_exp = subscription.grant_subscription(vip_uid, "monthly")
    assert subscription.get_tier_badge(vip_uid) == "🌙"
    assert init.user_details[vip_uid]["subscription_tier"] == "monthly"

    result = await award_weekly_leaderboard_prizes(bot=None)

    assert result["awarded_count"] == 1
    assert result["awarded_users"] == [vip_uid]

    # Must retain monthly tier
    assert init.user_details[vip_uid]["subscription_tier"] == "monthly"
    assert subscription.get_tier_badge(vip_uid) == "🌙"

    # Expiry must be extended by 1 day
    new_exp = init.user_details[vip_uid]["subscription_expires"]
    assert new_exp == current_exp + 86400


@pytest.mark.asyncio
async def test_weekly_leaderboard_job(monkeypatch):
    """Test JobQueue execution callback."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_context = MagicMock()
    mock_context.bot = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    uid = 9001
    init.user_details[uid] = {**_default_user(), "points": 100}

    await weekly_leaderboard_job(mock_context)
    assert subscription.is_subscribed(uid) is True


@pytest.mark.asyncio
async def test_weekly_reward_admin_command(monkeypatch):
    """Test manual trigger admin command."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    admin_uid = 99999
    init.ADMIN_IDS = [admin_uid]

    user_uid = 9002
    init.user_details[user_uid] = {**_default_user(), "current_streak": 15}

    update = MagicMock()
    update.effective_user.id = admin_uid
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.send_message = AsyncMock()

    await weekly_reward_admin_command(update, context)

    assert update.message.reply_text.called
    reply_text = update.message.reply_text.call_args[1]["text"]
    assert "Weekly Leaderboard Reward Triggered" in reply_text
    assert "Saturday 6:00 PM IST" in reply_text
    assert "1-day VIP" in reply_text
    assert subscription.is_subscribed(user_uid) is True


@pytest.mark.asyncio
async def test_pre_weekly_leaderboard_update_job(monkeypatch):
    """Test 5:59 PM IST pre-reward leaderboard update and data sync."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    mock_save = AsyncMock()
    monkeypatch.setattr("saveNload.save_user_data", mock_save)

    mock_context = MagicMock()
    await pre_weekly_leaderboard_update_job(mock_context)

    # Verifies user data sync was called
    assert mock_save.called


@pytest.mark.asyncio
async def test_saturday_countdown_and_explicit_messages(monkeypatch):
    """Verify Saturday 6:00 PM IST is explicitly declared in leaderboard header and countdown."""
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)

    uid = 9050
    init.user_details[uid] = {**_default_user(), "current_streak": 10}

    days, hours = get_weekly_reset_countdown()
    assert 0 <= days <= 7
    assert 0 <= hours <= 23

    text = await render_leaderboard_text("streaks", uid)
    assert "Every <b>Saturday at 6:00 PM IST</b>" in text
    assert "Top 3 win <b>1 Day Free VIP</b>!" in text
