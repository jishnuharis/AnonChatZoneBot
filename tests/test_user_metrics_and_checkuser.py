import time
import pytest
from unittest.mock import AsyncMock, MagicMock

import init
from commands.admin_commands import check_user
from commands.profile import _build_profile_text
from session_manager import end_chat_session
from relay import relay_message
from message import CHECKUSER_USAGE_TEXT, GIVE_VALID_USER_ID_TEXT, NO_RECORD_OF_USER_TEXT


@pytest.fixture(autouse=True)
def reset_globals():
    init.user_details.clear()
    init.waiting_users.clear()
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.session_start_times.clear()
    init.dirty_users.clear()
    init.ADMIN_IDS.clear()
    init.OWNER = "99999"


@pytest.mark.asyncio
async def test_checkuser_missing_args():
    admin_id = 99999
    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await check_user(update, context)
    update.message.reply_text.assert_called_once_with(CHECKUSER_USAGE_TEXT, parse_mode="HTML")


@pytest.mark.asyncio
async def test_checkuser_invalid_arg():
    admin_id = 99999
    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["not_an_id"]

    await check_user(update, context)
    update.message.reply_text.assert_called_once_with(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")


@pytest.mark.asyncio
async def test_checkuser_unknown_user_no_record_and_no_ghost_creation(monkeypatch):
    admin_id = 99999
    unknown_id = 123456789

    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [str(unknown_id)]

    # Mock get_user to return None (user not in DB)
    monkeypatch.setattr("saveNload.get_user", AsyncMock(return_value=None))

    await check_user(update, context)

    # Must reply with NO_RECORD_OF_USER_TEXT
    update.message.reply_text.assert_called_once_with(NO_RECORD_OF_USER_TEXT, parse_mode="HTML")
    # Must NOT create a ghost record in init.user_details
    assert unknown_id not in init.user_details


@pytest.mark.asyncio
async def test_checkuser_registered_user_display(monkeypatch):
    admin_id = 99999
    target_id = 555001

    created_timestamp = 1700000000.0  # Specific timestamp
    last_act = time.time() - 300  # 5 minutes ago

    user_data = {
        **init._default_user(),
        "created_at": created_timestamp,
        "last_active": last_act,
        "total_messages": 42,
        "total_chat_duration": 180.0,
        "gender": "M",
        "age": 25,
        "country": "US",
        "points": 10,
    }
    init.user_details[target_id] = user_data

    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [str(target_id)]

    await check_user(update, context)

    assert update.message.reply_text.called
    sent_text = update.message.reply_text.call_args[0][0]

    assert f"<b>User</b> <code>{target_id}</code>" in sent_text
    assert "Account Created:" in sent_text
    assert "Last Active: 5m ago" in sent_text
    assert "Total Messages: 42" in sent_text
    assert "Time in Chats: 3m" in sent_text


@pytest.mark.asyncio
async def test_checkuser_recent_activity_shows_just_now():
    admin_id = 99999
    target_id = 555002

    user_data = {
        **init._default_user(),
        "created_at": time.time() - 1000,
        "last_active": time.time() - 10,  # 10s ago
        "total_messages": 5,
        "gender": "F",
        "country": "UK",
    }
    init.user_details[target_id] = user_data

    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [str(target_id)]

    await check_user(update, context)

    sent_text = update.message.reply_text.call_args[0][0]
    assert "Last Active: Just now" in sent_text


@pytest.mark.asyncio
async def test_checkuser_includes_inflight_active_chat_duration():
    admin_id = 99999
    u1, u2 = 555003, 555004

    init.user_details[u1] = {
        **init._default_user(),
        "gender": "M",
        "country": "US",
        "total_chat_duration": 120.0,  # 2m stored
        "partner_id": u2,
    }
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 180  # 3m currently in active chat

    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [str(u1)]

    await check_user(update, context)

    sent_text = update.message.reply_text.call_args[0][0]
    # Total chat duration should be ~2m stored + ~3m current = ~5m
    assert "Time in Chats: 5m" in sent_text


@pytest.mark.asyncio
async def test_profile_displays_metrics_and_omits_last_active(monkeypatch):
    user_id = 777001
    created_ts = 1700000000.0  # 2023-11-14

    init.user_details[user_id] = {
        **init._default_user(),
        "gender": "M",
        "age": 22,
        "country": "Canada",
        "created_at": created_ts,
        "last_active": time.time() - 50,
        "total_messages": 88,
        "total_chat_duration": 3600.0,  # 1 hour
    }

    mock_context = MagicMock()
    profile_text = await _build_profile_text(
        user_id,
        mock_context,
        fallback_name="Test User",
        fallback_username="testuser",
    )

    # Must contain member since, messages sent, and time in chats
    assert "<b>Member Since:</b> 2023-11-14" in profile_text
    assert "<b>Messages Sent:</b> 88" in profile_text
    assert "<b>Time in Chats:</b> 1h" in profile_text

    # Must NOT contain Last Active
    assert "Last Active" not in profile_text


@pytest.mark.asyncio
async def test_profile_includes_inflight_duration():
    user_id = 777002
    partner_id = 777003

    init.user_details[user_id] = {
        **init._default_user(),
        "gender": "F",
        "age": 24,
        "country": "Germany",
        "total_chat_duration": 600.0,  # 10m
        "partner_id": partner_id,
    }
    init.active_pairs[user_id] = partner_id
    init.session_start_times[user_id] = time.time() - 300  # 5m in flight

    mock_context = MagicMock()
    profile_text = await _build_profile_text(
        user_id,
        mock_context,
        fallback_name="Alice",
    )

    # Total duration = 10m + 5m = 15m
    assert "<b>Time in Chats:</b> 15m" in profile_text
    assert "Last Active" not in profile_text


@pytest.mark.asyncio
async def test_relay_increments_total_messages_and_updates_last_active():
    u1, u2 = 888001, 888002
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100

    old_last_active = time.time() - 500
    init.user_details[u1]["last_active"] = old_last_active
    init.user_details[u1]["total_messages"] = 10

    update = MagicMock()
    update.effective_user.id = u1
    msg = MagicMock()
    msg.text = "Hello there!"
    msg.caption = None
    msg.photo = []
    msg.video = None
    msg.voice = None
    msg.video_note = None
    msg.sticker = None
    msg.animation = None
    msg.document = None
    msg.dice = None
    msg.audio = None
    msg.entities = []
    msg.caption_entities = []
    msg.reply_to_message = None
    msg.message_id = 101
    update.message = msg

    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=202))
    context.bot.send_chat_action = AsyncMock()

    await relay_message(update, context)

    assert init.user_details[u1]["total_messages"] == 11
    assert init.user_details[u1]["last_active"] > old_last_active
    assert u1 in init.dirty_users


@pytest.mark.asyncio
async def test_end_chat_session_accumulates_duration():
    u1, u2 = 999001, 999002
    init.user_details[u1] = {**init._default_user(), "total_chat_duration": 100.0}
    init.user_details[u2] = {**init._default_user(), "total_chat_duration": 50.0}

    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.active_sessions[u1] = "session-123"
    init.active_sessions[u2] = "session-123"

    # Chat started 60 seconds ago
    init.session_start_times[u1] = time.time() - 60.0
    init.session_start_times[u2] = init.session_start_times[u1]

    context = MagicMock()
    context.bot.send_message = AsyncMock()

    await end_chat_session(context, u1, reason="user_ended")

    # u1 duration should increase by ~60s: 100 + 60 = ~160
    assert 158.0 <= init.user_details[u1]["total_chat_duration"] <= 165.0
    # u2 duration should increase by ~60s: 50 + 60 = ~110
    assert 108.0 <= init.user_details[u2]["total_chat_duration"] <= 115.0

    assert u1 in init.dirty_users
    assert u2 in init.dirty_users


@pytest.mark.asyncio
async def test_decimal_support_in_profile_and_checkuser():
    from decimal import Decimal

    user_id = 999123
    dec_created = Decimal("1700000000.123")
    dec_last_active = Decimal(str(time.time() - 120))
    dec_total_msgs = Decimal("15")
    dec_duration = Decimal("300.5")

    init.user_details[user_id] = {
        **init._default_user(),
        "created_at": dec_created,
        "last_active": dec_last_active,
        "total_messages": dec_total_msgs,
        "total_chat_duration": dec_duration,
        "gender": "M",
        "age": 25,
        "country": "US",
    }

    # Verify /profile does not crash on Decimal
    mock_context = MagicMock()
    profile_text = await _build_profile_text(user_id, mock_context, fallback_name="DecUser")
    assert "<b>Member Since:</b> 2023-11-14" in profile_text
    assert "<b>Messages Sent:</b> 15" in profile_text
    assert "<b>Time in Chats:</b> 5m" in profile_text

    # Verify /checkuser does not crash on Decimal
    update = MagicMock()
    update.effective_user.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = [str(user_id)]

    await check_user(update, context)
    assert update.message.reply_text.called
    check_text = update.message.reply_text.call_args[0][0]
    assert "Account Created: <code>2023-11-14 22:13 UTC</code>" in check_text
    assert "Last Active: 2m ago" in check_text
    assert "Total Messages: 15" in check_text
    assert "Time in Chats: 5m" in check_text

