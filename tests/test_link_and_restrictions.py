import time
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram.constants import MessageEntityType

import init
from security import contains_link
from relay import relay_message, relay_edited_message
from commands.link import link_command
from message import LINK_RESTRICTED_TEXT, MEDIA_WARMUP_LOCKED_TEXT, LINK_NO_USERNAME_TEXT


def test_contains_link():
    # Regular text without links
    msg_normal = MagicMock(text="Hello partner! How are you doing today?", caption=None, entities=None, caption_entities=None)
    assert not contains_link(msg_normal)

    # Plain text with period at end of sentence
    msg_sentence = MagicMock(text="Nice weather. Really nice.", caption=None, entities=None, caption_entities=None)
    assert not contains_link(msg_sentence)

    # Standard URL
    msg_url = MagicMock(text="Check this out: https://example.com/page", caption=None, entities=None, caption_entities=None)
    assert contains_link(msg_url)

    # Telegram invite/channel link
    msg_tme = MagicMock(text="join t.me/mychannel", caption=None, entities=None, caption_entities=None)
    assert contains_link(msg_tme)

    # Telegram @username
    msg_handle = MagicMock(text="Add me @coolcat99", caption=None, entities=None, caption_entities=None)
    assert contains_link(msg_handle)

    # Domain name
    msg_domain = MagicMock(text="visit mywebsite.xyz now", caption=None, entities=None, caption_entities=None)
    assert contains_link(msg_domain)

    # Spaced domain bypass attempt
    msg_spaced = MagicMock(text="visit google . com", caption=None, entities=None, caption_entities=None)
    assert contains_link(msg_spaced)

    # Masked text_link entity
    entity = MagicMock(type=MessageEntityType.TEXT_LINK)
    msg_entity = MagicMock(text="click here", caption=None, entities=[entity], caption_entities=None)
    assert contains_link(msg_entity)

    # Caption with link
    msg_caption = MagicMock(text=None, caption="Look at https://myphoto.com", entities=None, caption_entities=None)
    assert contains_link(msg_caption)


@pytest.mark.asyncio
async def test_free_user_link_blocked_in_relay():
    u1, u2 = 8001, 8002
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100  # > 1 min in chat

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = "Join my telegram: https://t.me/spammer"
    mock_update.message.caption = None
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await relay_message(mock_update, mock_context)

    # Message to partner was NOT sent
    mock_context.bot.send_message.assert_not_called()
    # Alert with subscription upgrade was sent to u1
    mock_update.message.reply_text.assert_called_once()
    assert "Links and usernames cannot be shared" in mock_update.message.reply_text.call_args[1]["text"]
    reply_markup = mock_update.message.reply_text.call_args[1]["reply_markup"]
    assert reply_markup.inline_keyboard[0][0].callback_data == "sub|upgrade_prompt"


@pytest.mark.asyncio
async def test_paid_user_link_allowed_in_relay():
    u1, u2 = 8003, 8004
    u1_data = init._default_user()
    u1_data["subscription_expires"] = time.time() + 86400  # VIP active
    init.user_details[u1] = u1_data
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time()

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = "Check this cool website: https://example.com"
    mock_update.message.caption = None
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_chat_action = AsyncMock(return_value=True)
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))

    await relay_message(mock_update, mock_context)

    # Partner received message
    mock_context.bot.send_message.assert_called_once()
    assert mock_context.bot.send_message.call_args[1]["chat_id"] == u2


@pytest.mark.asyncio
async def test_free_user_media_warmup_lock():
    u1, u2 = 8005, 8006
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 20  # only 20 seconds into chat

    # 1. Sticker within 20s -> Blocked
    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = None
    mock_update.message.caption = None
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = MagicMock(file_id="sticker_123")
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_sticker = AsyncMock()

    await relay_message(mock_update, mock_context)

    mock_context.bot.send_sticker.assert_not_called()
    reply_text = mock_update.message.reply_text.call_args[1]["text"]
    assert "Media sharing unlocks" in reply_text
    assert "39s" in reply_text or "40s" in reply_text

    # 2. After 60 seconds (elapsed = 70s) -> Allowed
    init.session_start_times[u1] = time.time() - 70
    mock_update.message.reply_text.reset_mock()
    mock_context.bot.send_sticker = AsyncMock(return_value=MagicMock(message_id=1001))

    await relay_message(mock_update, mock_context)
    mock_context.bot.send_sticker.assert_called_once()


@pytest.mark.asyncio
async def test_paid_user_media_allowed_immediately():
    u1, u2 = 8007, 8008
    u1_data = init._default_user()
    u1_data["subscription_expires"] = time.time() + 86400  # VIP active
    init.user_details[u1] = u1_data
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 5  # only 5 seconds into chat

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = None
    mock_update.message.caption = None
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = MagicMock(file_id="sticker_vip")
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_sticker = AsyncMock(return_value=MagicMock(message_id=1002))

    await relay_message(mock_update, mock_context)
    mock_context.bot.send_sticker.assert_called_once()


@pytest.mark.asyncio
async def test_relay_edited_message_link_blocked_for_free():
    u1, u2 = 8009, 8010
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.message_map[u1] = {501: (u2, 601)}

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    edit_msg = MagicMock()
    edit_msg.message_id = 501
    edit_msg.text = "I edited this to say visit https://spam.com"
    edit_msg.caption = None
    edit_msg.entities = None
    edit_msg.caption_entities = None
    edit_msg.reply_text = AsyncMock()
    mock_update.edited_message = edit_msg

    mock_context = MagicMock()
    mock_context.bot.edit_message_text = AsyncMock()

    await relay_edited_message(mock_update, mock_context)

    # Edit was blocked on partner side
    mock_context.bot.edit_message_text.assert_not_called()
    edit_msg.reply_text.assert_called_once()
    assert "Links and usernames cannot be shared" in edit_msg.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_link_command():
    u1, u2 = 8011, 8012
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1

    # 1. 1-minute warmup lock for free user
    init.session_start_times[u1] = time.time() - 30
    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.effective_user.username = "testuser1"
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await link_command(mock_update, mock_context)
    mock_context.bot.send_message.assert_not_called()
    mock_update.message.reply_text.assert_called_once()
    assert "Profile sharing unlocks" in mock_update.message.reply_text.call_args[1]["text"]

    # 2. No username set after 60s
    init.session_start_times[u1] = time.time() - 70
    mock_update.effective_user.username = None
    mock_update.message.reply_text.reset_mock()

    await link_command(mock_update, mock_context)
    mock_context.bot.send_message.assert_not_called()
    mock_update.message.reply_text.assert_called_once()
    assert "don't have a Telegram username set" in mock_update.message.reply_text.call_args[1]["text"]

    # 3. Successful link button sent to partner
    mock_update.effective_user.username = "real_username"
    mock_update.message.reply_text.reset_mock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=2001))

    await link_command(mock_update, mock_context)

    # Partner got private button with URL
    mock_context.bot.send_message.assert_called_once()
    call_args = mock_context.bot.send_message.call_args
    assert call_args[1]["chat_id"] == u2
    assert "shared their Telegram profile" in call_args[1]["text"]
    markup = call_args[1]["reply_markup"]
    assert markup.inline_keyboard[0][0].url == "https://t.me/real_username"

    # Sender received confirmation
    mock_update.message.reply_text.assert_called_once()
    assert "shared with your partner" in mock_update.message.reply_text.call_args[1]["text"]
