import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import init
from init import _default_user
from subscription import (
    grant_vip_hours, is_subscribed, status_text
)
from rush_hour import (
    is_rush_hour_active, set_rush_hour_active, claim_rush_hour_reward,
    get_claimed_count, MAX_REWARD_WINNERS, rush_hour_command,
    start_rush_hour_job, end_rush_hour_job
)


@pytest.fixture(autouse=True)
def clean_state():
    init.user_details.clear()
    init.dirty_users.clear()
    init.active_pairs.clear()
    init.waiting_users.clear()
    set_rush_hour_active(False)
    yield
    set_rush_hour_active(False)


def test_grant_vip_hours():
    user_id = 99901
    init.user_details[user_id] = _default_user()

    assert not is_subscribed(user_id)
    exp = grant_vip_hours(user_id, hours=1.0)
    assert is_subscribed(user_id)
    assert exp > time.time()
    assert abs(exp - (time.time() + 3600)) < 5

    text = status_text(user_id)
    assert "Daily" in text
    assert "plan active" in text
    assert "hours left" in text or "minutes left" in text


def test_rush_hour_claim_limit():
    set_rush_hour_active(True)
    assert get_claimed_count() == 0

    # First 5 unique users should successfully claim
    for i in range(1, 6):
        uid = 1000 + i
        init.user_details[uid] = _default_user()
        claimed = claim_rush_hour_reward(uid)
        assert claimed is True
        assert is_subscribed(uid)

    assert get_claimed_count() == 5

    # 6th user should be rejected (limit reached)
    uid_6 = 1006
    init.user_details[uid_6] = _default_user()
    assert claim_rush_hour_reward(uid_6) is False
    assert not is_subscribed(uid_6)

    # Re-claiming by a winning user should return False
    assert claim_rush_hour_reward(1001) is False


def test_rush_hour_inactive_rejects_claim():
    set_rush_hour_active(False)
    uid = 2001
    init.user_details[uid] = _default_user()
    assert claim_rush_hour_reward(uid) is False
    assert not is_subscribed(uid)


@pytest.mark.asyncio
async def test_find_during_rush_hour_rewards_winner():
    from commands.find import find

    user_id = 3001
    init.user_details[user_id] = _default_user()
    init.user_details[user_id]["gender"] = "M"
    init.user_details[user_id]["age"] = 25
    init.user_details[user_id]["country"] = "US"

    set_rush_hour_active(True)

    mock_update = MagicMock()
    mock_update.effective_user.id = user_id
    mock_update.effective_chat.id = user_id
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await find(mock_update, mock_context)

    # User should now be subscribed for 1 hour
    assert is_subscribed(user_id)
    assert get_claimed_count() == 1

    # Reply should contain the Rush Hour winner text
    def get_text(c):
        return c.kwargs.get("text", "") or (c.args[0] if c.args else "")

    calls = mock_update.message.reply_text.call_args_list
    assert any("one of the first 5 users" in get_text(call) for call in calls)


@pytest.mark.asyncio
async def test_rush_hour_admin_command():
    admin_id = 12345
    init.ADMIN_IDS = [admin_id]

    mock_update = MagicMock()
    mock_update.effective_user.id = admin_id
    mock_update.effective_chat.id = admin_id
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.args = ["status"]

    def get_text(c):
        return c.kwargs.get("text", "") or (c.args[0] if c.args else "")

    # Status check
    await rush_hour_command(mock_update, mock_context)
    call_text = get_text(mock_update.message.reply_text.call_args)
    assert "Rush Hour Status" in call_text
    assert "INACTIVE" in call_text

    # Manually start
    mock_context.args = ["start"]
    with patch("rush_hour.broadcast_rush_hour", new_callable=AsyncMock) as mock_broadcast:
        await rush_hour_command(mock_update, mock_context)
        assert is_rush_hour_active() is True
        mock_broadcast.assert_awaited_once()

    # Manually end
    mock_context.args = ["end"]
    await rush_hour_command(mock_update, mock_context)
    assert is_rush_hour_active() is False
