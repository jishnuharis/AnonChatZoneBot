"""
Automated Matchmaking, Queue & Ban/Block Enforcement Tests.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import init
from matchmaking import enqueue_and_match, queue_sweep, _overlap_score
from moderation import apply_restriction, is_user_restricted
from session_manager import start_chat_session, is_in_chat
from saveNload import add_user_block, is_blocked_pairwise


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global queues and test state before each test."""
    init.waiting_users.clear()
    init.wait_started.clear()
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.recent_partners.clear()
    init.user_details.clear()
    init.dirty_users.clear()


@pytest.mark.asyncio
async def test_overlap_score_calculation():
    # User 1 has tags 0 and 1 (binary 0011 -> 3)
    # User 2 has tags 1 and 2 (binary 0110 -> 6)
    # Overlap is bit 1 (count = 1)
    init.user_details[1] = {"preferences": 0b0011}
    init.user_details[2] = {"preferences": 0b0110}
    init.user_details[3] = {"preferences": 0b1100}

    assert _overlap_score(1, 2) == 1
    assert _overlap_score(1, 3) == 0
    assert _overlap_score(2, 3) == 1


@pytest.mark.asyncio
async def test_banned_user_cannot_enter_queue():
    user_id = 999
    init.user_details[user_id] = init._default_user()
    init.user_details[user_id]["restricted_until"] = time.time() + 3600
    init.user_details[user_id]["restriction_reason"] = "Rule violation"

    mock_context = MagicMock()
    matched = await enqueue_and_match(mock_context, user_id)

    assert matched is False
    assert user_id not in init.waiting_users


@pytest.mark.asyncio
async def test_user_banned_while_in_queue_is_evicted():
    user1 = 101
    user2 = 102
    init.user_details[user1] = init._default_user()
    init.user_details[user2] = init._default_user()

    # User 1 joins queue
    init.waiting_users.append(user1)
    init.wait_started[user1] = time.time()

    # Admin bans User 1
    mock_context = MagicMock()
    await apply_restriction(user1, severity=5, reason="Spam", context=mock_context)

    # Assert User 1 was immediately evicted from queue
    assert user1 not in init.waiting_users
    assert user1 not in init.wait_started


@pytest.mark.asyncio
async def test_blocked_users_never_matched(monkeypatch):
    user1 = 201
    user2 = 202
    init.user_details[user1] = init._default_user()
    init.user_details[user2] = init._default_user()
    init.user_details[user1]["preferences"] = 0b1111
    init.user_details[user2]["preferences"] = 0b1111

    # Mock is_blocked_pairwise to return True
    async def mock_blocked(u1, u2):
        return True

    monkeypatch.setattr("matchmaking.is_blocked_pairwise", mock_blocked)

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # User 1 enqueues
    await enqueue_and_match(mock_context, user1)
    assert user1 in init.waiting_users

    # User 2 enqueues (should NOT match user 1 because blocked)
    matched = await enqueue_and_match(mock_context, user2)
    assert matched is False
    assert user1 in init.waiting_users
    assert user2 in init.waiting_users
    assert user1 not in init.active_pairs


@pytest.mark.asyncio
async def test_concurrent_enqueue_no_duplicate_match():
    users = list(range(1001, 1021)) # 20 users
    for u in users:
        init.user_details[u] = init._default_user()
        init.user_details[u]["preferences"] = 0b0011 # shared tags

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # Run 20 concurrent enqueue coroutines
    tasks = [enqueue_and_match(mock_context, u) for u in users]
    await asyncio.gather(*tasks)

    # Every paired user must have exactly 1 partner, reciprocal, and no one paired with self
    paired_count = len(init.active_pairs)
    assert paired_count == 20
    for u, partner in init.active_pairs.items():
        assert u != partner
        assert init.active_pairs[partner] == u
    assert len(init.waiting_users) == 0


@pytest.mark.asyncio
async def test_recent_partner_suppression():
    user1 = 301
    user2 = 302
    user3 = 303
    for u in (user1, user2, user3):
        init.user_details[u] = init._default_user()
        init.user_details[u]["preferences"] = 0b1111

    # User 1 and User 2 were recently matched
    init.recent_partners[user1] = [user2]

    # Enqueue user2 and user3
    init.waiting_users.extend([user2, user3])
    init.wait_started[user2] = time.time()
    init.wait_started[user3] = time.time()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # User 1 enqueues: should match with user3 instead of recent partner user2!
    await enqueue_and_match(mock_context, user1)
    assert init.active_pairs.get(user1) == user3


@pytest.mark.asyncio
async def test_block_expires_after_24_hours():
    """
    Blocks are active within 24 hours (86,400s), but expire and allow matching after 24 hours.
    """
    from saveNload import add_user_block, is_blocked_pairwise

    u1 = 205
    u2 = 206
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()

    # Block user 2
    await add_user_block(u1, u2)
    assert await is_blocked_pairwise(u1, u2) is True
    assert await is_blocked_pairwise(u2, u1) is True

    # Simulate 25 hours passed (90,000 seconds ago)
    init.user_details[u1]["blocked_users"][u2] = time.time() - 90000

    # Block should now be expired
    assert await is_blocked_pairwise(u1, u2) is False
    assert await is_blocked_pairwise(u2, u1) is False


@pytest.mark.asyncio
async def test_paid_user_gender_preference():
    """Paid user with Female gender preference only matches with Female candidates."""
    u_paid = 5001
    u_male = 5002
    u_female = 5003

    init.user_details[u_paid] = init._default_user()
    init.user_details[u_paid]["subscription_tier"] = "Monthly"
    init.user_details[u_paid]["subscription_expires"] = time.time() + 86400
    init.user_details[u_paid]["pref_gender"] = "F"  # Wants females only

    init.user_details[u_male] = init._default_user()
    init.user_details[u_male]["gender"] = "M"

    init.user_details[u_female] = init._default_user()
    init.user_details[u_female]["gender"] = "F"

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # Male is waiting in queue first
    init.waiting_users.append(u_male)
    init.wait_started[u_male] = time.time()

    # Paid user enqueues - must NOT match male
    matched = await enqueue_and_match(mock_context, u_paid)
    assert matched is False
    assert u_paid in init.waiting_users
    assert u_male in init.waiting_users

    # Female enqueues - matches with paid user!
    matched_female = await enqueue_and_match(mock_context, u_female)
    assert matched_female is True
    assert init.active_pairs.get(u_paid) == u_female
    assert init.active_pairs.get(u_female) == u_paid

    # Clean up
    init.active_pairs.pop(u_paid, None)
    init.active_pairs.pop(u_female, None)
    init.waiting_users.clear()


@pytest.mark.asyncio
async def test_paid_user_country_preference():
    """Paid user with Same Country preference only matches with same-country candidates."""
    u_paid = 6001
    u_other_country = 6002
    u_same_country = 6003

    init.user_details[u_paid] = init._default_user()
    init.user_details[u_paid]["subscription_tier"] = "Monthly"
    init.user_details[u_paid]["subscription_expires"] = time.time() + 86400
    init.user_details[u_paid]["country"] = "Japan"
    init.user_details[u_paid]["pref_country"] = "SAME"

    init.user_details[u_other_country] = init._default_user()
    init.user_details[u_other_country]["country"] = "Brazil"

    init.user_details[u_same_country] = init._default_user()
    init.user_details[u_same_country]["country"] = "Japan"

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # User from Brazil waiting in queue
    init.waiting_users.append(u_other_country)
    init.wait_started[u_other_country] = time.time()

    # Paid user enqueues - does NOT match Brazil user
    matched = await enqueue_and_match(mock_context, u_paid)
    assert matched is False

    # Same country user enqueues - matches!
    matched_same = await enqueue_and_match(mock_context, u_same_country)
    assert matched_same is True
    assert init.active_pairs.get(u_paid) == u_same_country

    # Clean up
    init.active_pairs.pop(u_paid, None)
    init.active_pairs.pop(u_same_country, None)
    init.waiting_users.clear()


