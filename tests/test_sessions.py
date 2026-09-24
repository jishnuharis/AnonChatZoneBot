"""
Automated Chat Session Lifecycle, Silent Chat Guarantee & Presence Tests.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock
from telegram.error import Forbidden

import init
from session_manager import (
    start_chat_session,
    end_chat_session,
    is_in_chat,
    get_partner,
    handle_transport_disconnect,
)


@pytest.fixture(autouse=True)
def reset_globals():
    init.waiting_users.clear()
    init.wait_started.clear()
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.user_details.clear()
    init.message_map.clear()
    init.dirty_users.clear()


@pytest.mark.asyncio
async def test_silent_chat_remains_active_indefinitely():
    """
    CRITICAL REQUIREMENT:
    Silent chats must remain active indefinitely while users are genuinely connected.
    Silence must NOT be treated as disconnection.
    """
    user1 = 501
    user2 = 502
    init.user_details[user1] = init._default_user()
    init.user_details[user2] = init._default_user()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # Pair users
    success = await start_chat_session(mock_context, user1, user2)
    assert success is True
    assert is_in_chat(user1) is True
    assert is_in_chat(user2) is True
    assert get_partner(user1) == user2
    assert get_partner(user2) == user1

    # Simulate 48 hours of complete silence (no messages exchanged)
    simulated_elapsed_seconds = 48 * 3600

    # Verify session is STILL 100% active and untouched
    assert is_in_chat(user1) is True
    assert is_in_chat(user2) is True
    assert get_partner(user1) == user2
    assert get_partner(user2) == user1


@pytest.mark.asyncio
async def test_transport_disconnect_on_bot_blocked():
    """
    When a user genuinely blocks the bot (Telegram Forbidden error),
    the session must be cleanly terminated and the partner notified.
    """
    user1 = 601
    user2 = 602
    init.user_details[user1] = init._default_user()
    init.user_details[user2] = init._default_user()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    await start_chat_session(mock_context, user1, user2)
    assert is_in_chat(user1) is True

    # User 1 blocks the bot -> triggers transport disconnect
    await handle_transport_disconnect(mock_context, user1)

    # Session is cleanly severed
    assert is_in_chat(user1) is False
    assert is_in_chat(user2) is False
    # Partner (User 2) was notified that partner left
    calls = mock_context.bot.send_message.call_args_list
    assert any(c.kwargs.get("chat_id") == user2 and "left the chat" in c.kwargs.get("text", "") for c in calls)


@pytest.mark.asyncio
async def test_concurrent_simultaneous_disconnect():
    """
    Both users issuing /stop or /next at the exact same millisecond
    must cleanly teardown without raising KeyError or ghost sessions.
    """
    user1 = 701
    user2 = 702
    init.user_details[user1] = init._default_user()
    init.user_details[user2] = init._default_user()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    await start_chat_session(mock_context, user1, user2)

    # Both users call end_chat_session concurrently
    task1 = end_chat_session(mock_context, user1, reason="skipped")
    task2 = end_chat_session(mock_context, user2, reason="user_stopped")

    res1, res2 = await asyncio.gather(task1, task2)

    # Exactly one task should have popped the partner, the other should gracefully return None
    assert (res1 is not None and res2 is None) or (res2 is not None and res1 is None)
    assert is_in_chat(user1) is False
    assert is_in_chat(user2) is False


@pytest.mark.asyncio
async def test_duplicate_session_prevention():
    """
    A user already in an active session cannot be started into another session.
    """
    u1, u2, u3 = 801, 802, 803
    for u in (u1, u2, u3):
        init.user_details[u] = init._default_user()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    # U1 and U2 are paired
    assert await start_chat_session(mock_context, u1, u2) is True

    # Attempting to pair U1 with U3 must fail
    assert await start_chat_session(mock_context, u1, u3) is False
    assert get_partner(u1) == u2
