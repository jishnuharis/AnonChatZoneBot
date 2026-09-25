import time
import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import init
from session_manager import start_chat_session, end_chat_session, is_in_chat, _partner_details_line
from commands.next import skip_partner, handle_undo_skip
from commands.call import call_command, handle_call_response, active_voice_calls
from handlers.friends import (
    send_friend_request, handle_friend_request_response,
    show_friends_menu, show_friend_card, handle_friend_card_actions,
    initiate_friend_connect, handle_connect_response, handle_friend_input_text
)
from handlers.transcript import handle_export_transcript
from subscription import get_friend_limit, TIERS
from saveNload import (
    deduplicate_friend_nickname, add_friend_pair_db, get_user_friends_db,
    remove_friend_pair_db, toggle_friend_favorite_db, update_friend_nickname_db,
    update_friend_note_db, get_friend_card_db, are_friends_db, _in_memory_friends
)


@pytest.fixture(autouse=True)
def clean_feature_state():
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.recent_skips.clear()
    init.session_messages.clear()
    init.pending_friend_requests.clear()
    init.pending_friend_connections.clear()
    init.waiting_users.clear()
    init.wait_started.clear()
    active_voice_calls.clear()
    _in_memory_friends.clear()
    yield
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.recent_skips.clear()
    init.session_messages.clear()
    init.pending_friend_requests.clear()
    init.pending_friend_connections.clear()
    init.waiting_users.clear()
    init.wait_started.clear()
    active_voice_calls.clear()
    _in_memory_friends.clear()


@pytest.mark.asyncio
async def test_accidental_skip_undo_button_success():
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))

    u1, u2 = 1001, 1002
    init.user_details[u1] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[u2] = {**init._default_user(), "gender": "F", "age": 21, "country": "US"}

    # Start active chat
    await start_chat_session(context, u1, u2)
    assert is_in_chat(u1) and is_in_chat(u2)

    # User 1 skips User 2
    update = MagicMock()
    update.effective_user.id = u1
    update.message.reply_text = AsyncMock()

    with patch("commands.next.find", new_callable=AsyncMock):
        await skip_partner(update, context)

    # Chat should be ended and skip recorded
    assert not is_in_chat(u1)
    assert u1 in init.recent_skips
    assert init.recent_skips[u1][0] == u2

    # User 1 taps Undo Skip within 60s
    cb_update = MagicMock()
    cb_update.effective_user.id = u1
    cb_update.callback_query.data = f"undoskip|{u2}"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await handle_undo_skip(cb_update, context)

    # Successfully reconnected!
    assert is_in_chat(u1)
    assert is_in_chat(u2)
    assert init.active_pairs.get(u1) == u2
    assert u1 not in init.recent_skips
    cb_update.callback_query.edit_message_text.assert_called_once()
    assert "reconnected" in cb_update.callback_query.edit_message_text.call_args[1]["text"].lower()


@pytest.mark.asyncio
async def test_accidental_skip_undo_expired():
    context = MagicMock()
    u1, u2 = 2001, 2002
    init.recent_skips[u1] = (u2, time.time() - 65)  # 65s ago

    cb_update = MagicMock()
    cb_update.effective_user.id = u1
    cb_update.callback_query.data = f"undoskip|{u2}"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await handle_undo_skip(cb_update, context)

    assert not is_in_chat(u1)
    assert "expired" in cb_update.callback_query.edit_message_text.call_args[1]["text"].lower()


@pytest.mark.asyncio
async def test_vip_gender_peek_only_for_subscribers():
    u_free = 3001
    u_vip = 3002
    partner = 3003

    init.user_details[u_free] = init._default_user()
    init.user_details[u_vip] = init._default_user()
    init.user_details[partner] = init._default_user()

    init.user_details[partner]["gender"] = "F"
    init.user_details[partner]["age"] = 22
    init.user_details[partner]["country"] = "Japan"

    # Free user: empty string (100% anonymous)
    init.user_details[u_free]["subscription_expires"] = None
    line_free = _partner_details_line(u_free, partner)
    assert line_free == ""

    # VIP user: gets gender peek only (no age, no country, no bio)
    init.user_details[u_vip]["subscription_expires"] = time.time() + 86400
    line_vip = _partner_details_line(u_vip, partner)
    assert "VIP Perk" in line_vip
    assert "Female" in line_vip
    assert "Japan" not in line_vip
    assert "22" not in line_vip


@pytest.mark.asyncio
async def test_friend_tier_limits():
    uid = 4001
    init.user_details[uid] = init._default_user()

    # Free tier: 16
    assert get_friend_limit(uid) == 16

    # Tier 1 (daily, priority=1): 16 + 16 = 32
    init.user_details[uid]["subscription_expires"] = time.time() + 86400
    init.user_details[uid]["subscription_tier"] = "daily"
    assert get_friend_limit(uid) == 32

    # Tier 2 (weekly, priority=2): 16 + 32 = 48
    init.user_details[uid]["subscription_tier"] = "weekly"
    assert get_friend_limit(uid) == 48


@pytest.mark.asyncio
async def test_roman_numeral_deduplication():
    u = 5001
    # First time adding "Bestie"
    name1 = await deduplicate_friend_nickname(u, "Bestie")
    assert name1 == "Bestie"
    await add_friend_pair_db(u, 9001, name1, "Other")

    # Second time adding "Bestie" -> Old becomes "Bestie I", new becomes "Bestie II"
    name2 = await deduplicate_friend_nickname(u, "Bestie")
    assert name2 == "Bestie II"
    await add_friend_pair_db(u, 9002, name2, "Other")

    card1 = await get_friend_card_db(u, 9001)
    assert card1["custom_name"] == "Bestie I"

    # Third time adding "Bestie" -> becomes "Bestie III"
    name3 = await deduplicate_friend_nickname(u, "Bestie")
    assert name3 == "Bestie III"


@pytest.mark.asyncio
async def test_mutual_friend_removal():
    u1, u2 = 6001, 6002
    await add_friend_pair_db(u1, u2, "Friend A", "Friend B")

    assert await are_friends_db(u1, u2)
    assert await are_friends_db(u2, u1)

    # Remove friendship
    await remove_friend_pair_db(u1, u2)
    assert not await are_friends_db(u1, u2)
    assert not await are_friends_db(u2, u1)


@pytest.mark.asyncio
async def test_friend_connect_busy_and_free_flow():
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))

    u_a, u_b, u_c = 7001, 7002, 7003
    init.user_details[u_a] = init._default_user()
    init.user_details[u_b] = init._default_user()
    init.user_details[u_c] = init._default_user()

    await add_friend_pair_db(u_a, u_b, "Buddy B", "Buddy A")

    # Case 1: Friend B is in active chat with User C
    await start_chat_session(context, u_b, u_c)
    assert is_in_chat(u_b)

    query = MagicMock()
    query.data = f"fconn|{u_b}|0"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.effective_user.id = u_a
    update.callback_query = query

    await initiate_friend_connect(update, context, u_b, page=0)

    # User A gets notice that B is busy
    assert "currently in another chat" in query.edit_message_text.call_args[1]["text"]
    # User B gets informational ping without buttons
    context.bot.send_message.assert_called_with(
        chat_id=u_b,
        text="🔔 <b>Your friend Buddy A wants to chat with you!</b>",
        parse_mode="HTML"
    )

    # Case 2: Friend B ends chat and is now free
    await end_chat_session(context, u_b)
    assert not is_in_chat(u_b)

    context.bot.send_message.reset_mock()
    query.edit_message_text.reset_mock()

    await initiate_friend_connect(update, context, u_b, page=0)

    # User B gets prompt with inline buttons
    assert context.bot.send_message.called
    call_args = context.bot.send_message.call_args
    assert call_args[1]["chat_id"] == u_b
    assert "wants to chat with you" in call_args[1]["text"]
    assert call_args[1]["reply_markup"] is not None

    # Retrieve connect request id
    conn_id = list(init.pending_friend_connections.keys())[0]

    # Friend B accepts
    acc_query = MagicMock()
    acc_query.data = f"f_c_acc|{conn_id}"
    acc_query.answer = AsyncMock()
    acc_query.edit_message_text = AsyncMock()
    acc_update = MagicMock()
    acc_update.effective_user.id = u_b
    acc_update.callback_query = acc_query

    await handle_connect_response(acc_update, context)

    # Now both are in an active friend chat session!
    assert is_in_chat(u_a)
    assert is_in_chat(u_b)
    assert init.active_pairs.get(u_a) == u_b
    assert "accepted" in acc_query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_transcript_export():
    context = MagicMock()
    context.bot.send_document = AsyncMock(return_value=MagicMock(message_id=888))

    session_id = "test-session-123"
    u1, u2 = 8001, 8002

    init.session_messages[session_id] = [
        (u1, "Hello from u1!", time.time() - 30),
        (u2, "Hey from u2, great to meet you!", time.time() - 20),
    ]

    query = MagicMock()
    query.data = f"export_chat|{session_id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.effective_user.id = u1
    update.callback_query = query

    await handle_export_transcript(update, context)

    # File was generated and sent
    assert context.bot.send_document.called
    doc_args = context.bot.send_document.call_args[1]
    assert doc_args["chat_id"] == u1
    assert "AnonChat_" in doc_args["filename"]

    # Verify transcript content
    doc_bytes = doc_args["document"].getvalue().decode("utf-8")
    assert "Hello from u1!" in doc_bytes
    assert "Hey from u2" in doc_bytes
    assert "100% Anonymized" in doc_bytes


@pytest.mark.asyncio
async def test_anonymous_voice_call_flow():
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=777))

    u1, u2 = 9001, 9002
    init.user_details[u1] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[u2] = {**init._default_user(), "gender": "F", "age": 21, "country": "US"}

    await start_chat_session(context, u1, u2)
    session_id = init.active_sessions.get(u1)
    context.bot.send_message.reset_mock()

    # User 1 initiates /call
    update = MagicMock()
    update.effective_user.id = u1
    update.message.reply_text = AsyncMock()

    await call_command(update, context)

    # User 2 gets call prompt
    assert context.bot.send_message.called
    send_args = context.bot.send_message.call_args[1]
    assert send_args["chat_id"] == u2
    assert "Incoming Anonymous Voice Call" in send_args["text"]

    # User 2 accepts call
    cb_query = MagicMock()
    cb_query.data = f"call_acc|{session_id}"
    cb_query.answer = AsyncMock()
    cb_query.edit_message_text = AsyncMock()
    cb_update = MagicMock()
    cb_update.effective_user.id = u2
    cb_update.callback_query = cb_query

    await handle_call_response(cb_update, context)

    # Call marked active and WebApp join buttons sent to both users
    assert active_voice_calls[session_id]["status"] == "active"
    assert "Call Connected" in cb_query.edit_message_text.call_args[1]["text"]
