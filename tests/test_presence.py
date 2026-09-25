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
async def test_in_chat_keyboard_nudge_only_and_relay():
    """Verify that in-chat keyboard contains ONLY 'Nudge your partner!' to prevent accidental skips, and relay intercepts it."""
    from session_manager import IN_CHAT_KEYBOARD
    from relay import relay_message

    # 1. Keyboard verification
    assert len(IN_CHAT_KEYBOARD.keyboard) == 1
    assert [b.text for b in IN_CHAT_KEYBOARD.keyboard[0]] == ["Nudge your partner!"]

    # 2. Relay interception verification
    u1, u2 = 9981, 9982
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    _nudge_timestamps.pop(u1, None)

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = "Nudge your partner!"
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

    # Clean up
    init.active_pairs.pop(u1, None)
    init.active_pairs.pop(u2, None)

