import time
import pytest
from unittest.mock import AsyncMock, MagicMock

import init
from commands.nudge import handle_nudge, status_command, NUDGE_COOLDOWN_SECONDS, _nudge_timestamps
from commands.admin_commands import broadcast
from session_manager import start_chat_session, end_chat_session


@pytest.mark.asyncio
async def test_nudge_not_in_chat():
    """Nudging when not in a chat should return an error message."""
    user_id = 9901
    init.user_details[user_id] = init._default_user()
    init.active_pairs.pop(user_id, None)

    mock_update = MagicMock()
    mock_update.effective_user.id = user_id
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()

    await handle_nudge(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    args, kwargs = mock_update.message.reply_text.call_args
    assert "not in a chat" in kwargs.get("text", "").lower()


@pytest.mark.asyncio
async def test_nudge_in_chat_and_cooldown():
    """Nudging in an active chat delivers to partner and enforces cooldown."""
    u1, u2 = 9902, 9903
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    _nudge_timestamps.pop(u1, None)

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=101))
    mock_context.bot.send_chat_action = AsyncMock(return_value=True)

    # First nudge: succeeds
    await handle_nudge(mock_update, mock_context)
    mock_context.bot.send_chat_action.assert_called_once_with(chat_id=u2, action="typing")
    mock_context.bot.send_message.assert_called_once()
    assert "Your partner is nudging you" in mock_context.bot.send_message.call_args[1]["text"]

    # Second immediate nudge: throttled by cooldown
    mock_update.message.reply_text.reset_mock()
    mock_context.bot.send_message.reset_mock()
    await handle_nudge(mock_update, mock_context)
    mock_context.bot.send_message.assert_not_called()
    assert "Please wait" in mock_update.message.reply_text.call_args[1]["text"]

    # Clean up
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)


@pytest.mark.asyncio
async def test_status_command():
    """Status command accurately reports partner activity timestamp."""
    u1, u2 = 9904, 9905
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.last_activity[u2] = time.time() - 45  # 45 seconds ago

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()

    await status_command(mock_update, mock_context)
    mock_update.message.reply_text.assert_called_once()
    text = mock_update.message.reply_text.call_args[1]["text"]
    assert "Partner Status:" in text
    assert "Connected" in text
    assert "45s ago" in text

    # Clean up
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)


@pytest.mark.asyncio
async def test_channel_broadcast(monkeypatch):
    """When ANNOUNCEMENT_CHANNEL is configured, /broadcast posts directly to the channel."""
    monkeypatch.setenv("ANNOUNCEMENT_CHANNEL", "@MyTestChannel")

    admin_id = 99999
    init.OWNER = admin_id

    mock_update = MagicMock()
    mock_update.effective_user.id = admin_id
    mock_update.message.text = "/broadcast Big update released!"
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=200))

    await broadcast(mock_update, mock_context)
    mock_context.bot.send_message.assert_called_once_with(
        chat_id="@MyTestChannel",
        text="Big update released!",
        parse_mode="HTML"
    )
    mock_update.message.reply_text.assert_called_once()
    reply_args = mock_update.message.reply_text.call_args
    reply_text = reply_args[0][0] if reply_args[0] else reply_args[1].get("text", "")
    assert "posted to channel @mytestchannel" in reply_text.lower()


@pytest.mark.asyncio
async def test_in_chat_keyboard_and_relay_interceptions():
    """Verify that in-chat keyboard has 3 rows (Nudge, Stop/Gift/Next, Subscription/Games) with is_persistent=False, and relay intercepts buttons."""
    from session_manager import IN_CHAT_KEYBOARD, IDLE_KEYBOARD
    from relay import relay_message

    # 1. Keyboard verification
    assert len(IN_CHAT_KEYBOARD.keyboard) == 3
    assert [b.text for b in IN_CHAT_KEYBOARD.keyboard[0]] == ["👋 Nudge your partner!"]
    assert [b.text for b in IN_CHAT_KEYBOARD.keyboard[1]] == ["🛑 Stop", "🎁 Gift", "⏭️ Next"]
    assert [b.text for b in IN_CHAT_KEYBOARD.keyboard[2]] == ["⭐ Subscription", "🎮 Games"]
    assert IN_CHAT_KEYBOARD.resize_keyboard is True
    assert IN_CHAT_KEYBOARD.is_persistent is False

    # 2. Idle keyboard verification
    assert len(IDLE_KEYBOARD.keyboard) == 2
    assert [b.text for b in IDLE_KEYBOARD.keyboard[0]] == ["🔍 Find Partner"]
    assert [b.text for b in IDLE_KEYBOARD.keyboard[1]] == ["⭐ Subscription", "👤 Profile"]
    assert IDLE_KEYBOARD.resize_keyboard is True
    assert IDLE_KEYBOARD.is_persistent is False

    # 3. Relay interception verification: Nudge
    u1, u2 = 9981, 9982
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    _nudge_timestamps.pop(u1, None)

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = "👋 Nudge your partner!"
    mock_update.message.caption = None
    mock_update.message.photo = []
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.animation = None
    mock_update.message.sticker = None
    mock_update.message.contact = None
    mock_update.message.location = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_chat_action = AsyncMock(return_value=True)
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=301))

    await relay_message(mock_update, mock_context)

    # Nudge was sent to u2, NOT relayed as normal text
    mock_context.bot.send_message.assert_called_once()
    send_args = mock_context.bot.send_message.call_args[1]
    assert send_args["chat_id"] == u2
    assert "Your partner is nudging you" in send_args["text"]

    # Also verify non-emoji variation is intercepted cleanly
    _nudge_timestamps.pop(u1, None)
    mock_context.bot.send_message.reset_mock()
    mock_update.message.text = "Nudge your partner!"
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_message.assert_called_once()
    assert mock_context.bot.send_message.call_args[1]["chat_id"] == u2

    # Clean up
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)


@pytest.mark.asyncio
async def test_in_chat_and_idle_buttons_intercepted():
    """Verify in-chat buttons (Stop, Gift, Next, Sub, Games) and idle buttons (Find, Sub, Profile) are intercepted."""
    from relay import relay_message
    from unittest.mock import patch

    u1, u2 = 9983, 9984
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_context = MagicMock()

    from security import _user_msg_times

    # 1. In-chat buttons
    with patch("commands.stop.stop", new_callable=AsyncMock) as mock_stop:
        _user_msg_times[u1].clear()
        mock_update.message.text = "🛑 Stop"
        await relay_message(mock_update, mock_context)
        mock_stop.assert_called_once()

    with patch("commands.gift.gift_command", new_callable=AsyncMock) as mock_gift:
        _user_msg_times[u1].clear()
        mock_update.message.text = "🎁 Gift"
        await relay_message(mock_update, mock_context)
        mock_gift.assert_called_once()

    with patch("commands.next.skip_partner", new_callable=AsyncMock) as mock_next:
        _user_msg_times[u1].clear()
        mock_update.message.text = "⏭️ Next"
        await relay_message(mock_update, mock_context)
        mock_next.assert_called_once()

    with patch("commands.subscribe.show_subscribe_menu", new_callable=AsyncMock) as mock_sub:
        _user_msg_times[u1].clear()
        mock_update.message.text = "⭐ Subscription"
        await relay_message(mock_update, mock_context)
        mock_sub.assert_called_once()

    with patch("commands.games.games_menu", new_callable=AsyncMock) as mock_games:
        _user_msg_times[u1].clear()
        mock_update.message.text = "🎮 Games"
        await relay_message(mock_update, mock_context)
        mock_games.assert_called_once()

    # Disconnect pair -> now user is idle
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)

    # 2. Idle buttons
    with patch("commands.find.find", new_callable=AsyncMock) as mock_find:
        _user_msg_times[u1].clear()
        mock_update.message.text = "🔍 Find Partner"
        await relay_message(mock_update, mock_context)
        mock_find.assert_called_once()

    with patch("commands.subscribe.show_subscribe_menu", new_callable=AsyncMock) as mock_sub_idle:
        _user_msg_times[u1].clear()
        mock_update.message.text = "⭐ Subscription"
        await relay_message(mock_update, mock_context)
        mock_sub_idle.assert_called_once()

    with patch("commands.profile.show_profile", new_callable=AsyncMock) as mock_prof:
        _user_msg_times[u1].clear()
        mock_update.message.text = "👤 Profile"
        await relay_message(mock_update, mock_context)
        mock_prof.assert_called_once()



@pytest.mark.asyncio
async def test_relay_edited_message():
    """Verify that when a user edits their message or caption, it edits the partner's corresponding message in real-time."""
    from relay import relay_edited_message
    from telegram.error import BadRequest

    u1, u2 = 7701, 7702
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.message_map[u1] = {100: (u2, 200), 101: (u2, 201)}

    # 1. Edit text
    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.edited_message.message_id = 100
    mock_update.edited_message.text = "Hello (edited!)"
    mock_update.edited_message.caption = None

    mock_context = MagicMock()
    mock_context.bot.edit_message_text = AsyncMock(return_value=True)
    mock_context.bot.edit_message_caption = AsyncMock(return_value=True)

    await relay_edited_message(mock_update, mock_context)
    mock_context.bot.edit_message_text.assert_called_once_with(
        chat_id=u2,
        message_id=200,
        text="Hello (edited!)"
    )

    # 2. Edit caption
    mock_update.edited_message.message_id = 101
    mock_update.edited_message.text = None
    mock_update.edited_message.caption = "New media caption"

    await relay_edited_message(mock_update, mock_context)
    mock_context.bot.edit_message_caption.assert_called_once_with(
        chat_id=u2,
        message_id=201,
        caption="New media caption"
    )

    # 3. Benign edit error handling (message can't be edited)
    mock_context.bot.edit_message_text.side_effect = BadRequest("Message can't be edited")
    mock_update.edited_message.message_id = 100
    mock_update.edited_message.text = "Attempting to edit old message"
    # Must not raise an exception
    await relay_edited_message(mock_update, mock_context)

    # Clean up
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)
    init.message_map.pop(u1, None)


@pytest.mark.asyncio
async def test_broadcast_reply_and_entity_fallback(monkeypatch):
    """Verify reply-to-broadcast copies message and entity errors fallback to plain text."""
    from commands.admin_commands import broadcast
    from telegram.error import BadRequest

    monkeypatch.setenv("ANNOUNCEMENT_CHANNEL", "@MyTestChannel")
    admin_id = 88888
    init.ADMIN_IDS.add(admin_id)

    # 1. Reply to broadcast
    mock_update = MagicMock()
    mock_update.effective_user.id = admin_id
    mock_update.effective_chat.id = 12345
    mock_update.message.text = "/broadcast"
    mock_update.message.caption = None
    mock_update.message.photo = []
    # Explicitly set mock reply
    reply_target = MagicMock()
    reply_target.message_id = 456
    mock_update.message.reply_to_message = reply_target
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.copy_message = AsyncMock(return_value=MagicMock(message_id=501))
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=502))

    await broadcast(mock_update, mock_context)
    mock_context.bot.copy_message.assert_called_once_with(
        chat_id="@MyTestChannel",
        from_chat_id=12345,
        message_id=456
    )

    # 2. Entity parse failure triggers clean plain text fallback
    mock_update.message.reply_to_message = None
    mock_update.message.text = "/broadcast <b>Broken tag message"
    
    # First call with HTML raises entity error, second call with plain succeeds
    first_call = True
    async def mock_send_message(*args, **kwargs):
        nonlocal first_call
        if kwargs.get("parse_mode") == "HTML":
            raise BadRequest("Can't parse entities: can't find end tag")
        return MagicMock(message_id=701)

    mock_context.bot.send_message = AsyncMock(side_effect=mock_send_message)
    await broadcast(mock_update, mock_context)

    # Verify send_message was called twice (HTML failed -> Plain text fallback succeeded)
    assert mock_context.bot.send_message.call_count == 2
    second_call_kwargs = mock_context.bot.send_message.call_args_list[1][1]
    assert second_call_kwargs["parse_mode"] is None
    assert second_call_kwargs["text"] == "Broken tag message"


@pytest.mark.asyncio
async def test_broadcast_photo_caption(monkeypatch):
    """Verify that sending a photo directly with /broadcast caption posts photo to channel."""
    from commands.admin_commands import broadcast

    monkeypatch.setenv("ANNOUNCEMENT_CHANNEL", "@MyTestChannel")
    admin_id = 99911
    init.ADMIN_IDS.add(admin_id)

    mock_update = MagicMock()
    mock_update.effective_user.id = admin_id
    mock_update.message.text = None
    mock_update.message.caption = "/broadcast 🚀 Special Announcement!"
    photo_mock = MagicMock()
    photo_mock.file_id = "test_photo_file_id_999"
    mock_update.message.photo = [photo_mock]
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_photo = AsyncMock(return_value=MagicMock(message_id=888))

    await broadcast(mock_update, mock_context)
    mock_context.bot.send_photo.assert_called_once_with(
        chat_id="@MyTestChannel",
        photo="test_photo_file_id_999",
        caption="🚀 Special Announcement!",
        parse_mode="HTML"
    )

    # Also test photo with ONLY "/broadcast" caption (no caption text)
    mock_context.bot.send_photo.reset_mock()
    mock_update.message.caption = "/broadcast"
    await broadcast(mock_update, mock_context)
    mock_context.bot.send_photo.assert_called_once_with(
        chat_id="@MyTestChannel",
        photo="test_photo_file_id_999"
    )


@pytest.mark.asyncio
async def test_broadcast_test_mode_owner_only(monkeypatch):
    """Verify /broadcast test delivers only to the caller/owner and does NOT touch users or channels."""
    from commands.admin_commands import broadcast

    monkeypatch.setenv("ANNOUNCEMENT_CHANNEL", "@MyTestChannel")
    admin_id = 77777
    init.ADMIN_IDS.add(admin_id)

    mock_update = MagicMock()
    mock_update.effective_user.id = admin_id
    mock_update.effective_chat.id = admin_id
    mock_update.message.text = "/broadcast test <b>Preview announcement!</b>"
    mock_update.message.caption = None
    mock_update.message.photo = []
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=901))
    mock_context.bot.copy_message = AsyncMock()

    await broadcast(mock_update, mock_context)

    # Must be sent ONLY to the caller/owner's chat_id
    mock_context.bot.send_message.assert_called_once_with(
        chat_id=admin_id,
        text="<b>Preview announcement!</b>",
        parse_mode="HTML"
    )
    # Channel should NOT be touched
    assert mock_context.bot.copy_message.call_count == 0

    # User receives test confirmation
    reply_calls = mock_update.message.reply_text.call_args_list
    assert any("Test Mode" in call.args[0] for call in reply_calls)




