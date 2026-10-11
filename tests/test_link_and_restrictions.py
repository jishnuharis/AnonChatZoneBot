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
    assert "69s" in reply_text or "70s" in reply_text

    # 2. After 90 seconds (elapsed = 100s) -> Allowed
    init.session_start_times[u1] = time.time() - 100
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

    # 1. 90-second warmup lock for free user
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

    # 2. No username set after 90s
    init.session_start_times[u1] = time.time() - 100
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


@pytest.mark.asyncio
async def test_document_and_audio_consume_credits():
    from subscription import daily_credits_used
    u1, u2 = 8013, 8014
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100  # Past 90s warmup

    # 1. Send Document
    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = None
    mock_update.message.caption = "my_doc"
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = MagicMock(file_id="doc_123")
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_document = AsyncMock(return_value=MagicMock(message_id=3001))
    mock_context.bot.send_chat_action = AsyncMock()

    assert daily_credits_used(u1) == 0
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_document.assert_called_once()
    assert daily_credits_used(u1) == 1

    # 2. Send Audio
    mock_update.message.document = None
    mock_update.message.audio = MagicMock(file_id="audio_456")
    mock_context.bot.send_audio = AsyncMock(return_value=MagicMock(message_id=3002))

    await relay_message(mock_update, mock_context)
    mock_context.bot.send_audio.assert_called_once()
    assert daily_credits_used(u1) == 2


@pytest.mark.asyncio
async def test_document_and_audio_blocked_when_credits_exhausted():
    u1, u2 = 8015, 8016
    u1_data = init._default_user()
    today = time.strftime("%Y-%m-%d", time.gmtime())
    u1_data["daily_credits_reset_day"] = today
    u1_data["daily_credits_used"] = 32  # Free limit reached
    init.user_details[u1] = u1_data
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100  # Past 90s warmup

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
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = MagicMock(file_id="doc_blocked")
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_document = AsyncMock()
    mock_context.bot.send_audio = AsyncMock()
    mock_context.bot.send_chat_action = AsyncMock()

    # Blocked document
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_document.assert_not_called()
    assert "file" in mock_update.message.reply_text.call_args[1]["text"]

    # Blocked audio
    mock_update.message.document = None
    mock_update.message.audio = MagicMock(file_id="audio_blocked")
    mock_update.message.reply_text.reset_mock()

    await relay_message(mock_update, mock_context)
    mock_context.bot.send_audio.assert_not_called()
    assert "audio file" in mock_update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_dice_and_non_text_blocked_during_warmup():
    from subscription import daily_credits_used
    u1, u2 = 8017, 8018
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 30  # 30s into chat (< 90s)

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
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = MagicMock(emoji="🎲")
    mock_update.message.reply_to_message = None
    mock_update.message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.bot.send_dice = AsyncMock()
    mock_context.bot.send_chat_action = AsyncMock()

    # 1. Dice blocked during 90s warmup
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_dice.assert_not_called()
    assert "Media sharing unlocks" in mock_update.message.reply_text.call_args[1]["text"]

    # 2. Dice allowed after 90s warmup without consuming credits
    init.session_start_times[u1] = time.time() - 100
    mock_context.bot.send_dice = AsyncMock(return_value=MagicMock(message_id=4001))
    mock_update.message.reply_text.reset_mock()

    await relay_message(mock_update, mock_context)
    mock_context.bot.send_dice.assert_called_once()
    assert daily_credits_used(u1) == 0


def test_handles_without_at_and_anti_scam_detection():
    from security import contains_prohibited_contact, is_scam_or_phishing_text

    # Positive handle detection without '@'
    assert contains_prohibited_contact("tg: johndoe")
    assert contains_prohibited_contact("insta: cute_girl")
    assert contains_prohibited_contact("snap: cutie99")
    assert contains_prohibited_contact("tele: user123")
    assert contains_prohibited_contact("my tg is alex")
    assert contains_prohibited_contact("my username is coolguy99")
    assert contains_prohibited_contact("username: coolguy99")
    assert contains_prohibited_contact("add me on tg johndoe")
    assert contains_prohibited_contact("dm me on insta saraah")

    # Obfuscated dots & links
    assert contains_prohibited_contact("visit google(dot)com now")
    assert contains_prohibited_contact("visit t . me")

    # Phone numbers
    assert contains_prohibited_contact("+1 555 123 4567")
    assert contains_prohibited_contact("9876543210")
    assert contains_prohibited_contact("9 8 7 6 5 4 3 2 1 0")

    # Scam phrases
    assert is_scam_or_phishing_text("crypto investment earn $500 daily")
    assert is_scam_or_phishing_text("free stars bot send stars get double")
    assert is_scam_or_phishing_text("bit.ly/scamlink")

    # Negative cases (ordinary conversational phrases should NOT be flagged)
    assert not contains_prohibited_contact("Hello partner! How are you doing today?")
    assert not contains_prohibited_contact("Instagram is a popular app today")
    assert not contains_prohibited_contact("Telegram is great for privacy")
    assert not contains_prohibited_contact("Snap of the fingers")
    assert not contains_prohibited_contact("I am 22 years old and love gaming")
    assert not contains_prohibited_contact("It costs 100 dollars")
    assert not contains_prohibited_contact("my_doc")


@pytest.mark.asyncio
async def test_media_spoiler_protection_honors_recipient_preference():
    u1, u2 = 8019, 8020
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100

    # Ensure u1 has daily credit
    init.user_details[u1]["daily_credits_used"] = 0

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = None
    mock_update.message.caption = None
    mock_update.message.entities = None
    mock_update.message.caption_entities = None
    photo_mock = MagicMock()
    photo_mock.file_id = "photo_123"
    mock_update.message.photo = [photo_mock]
    mock_update.message.video = None
    mock_update.message.voice = None
    mock_update.message.video_note = None
    mock_update.message.sticker = None
    mock_update.message.animation = None
    mock_update.message.document = None
    mock_update.message.audio = None
    mock_update.message.dice = None
    mock_update.message.reply_to_message = None

    mock_context = MagicMock()
    mock_context.bot.send_photo = AsyncMock(return_value=MagicMock(message_id=5001))
    mock_context.bot.send_chat_action = AsyncMock()

    # Case 1: Recipient has media_spoiler: True (default) -> has_spoiler=True
    init.user_details[u2]["media_spoiler"] = True
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_photo.assert_called_once()
    assert mock_context.bot.send_photo.call_args[1]["has_spoiler"] is True

    # Case 2: Recipient disabled media_spoiler -> has_spoiler=False
    init.user_details[u2]["media_spoiler"] = False
    init.user_details[u1]["daily_credits_used"] = 0
    mock_context.bot.send_photo.reset_mock()
    await relay_message(mock_update, mock_context)
    mock_context.bot.send_photo.assert_called_once()
    assert mock_context.bot.send_photo.call_args[1]["has_spoiler"] is False


@pytest.mark.asyncio
async def test_scam_message_blocked_in_relay():
    u1, u2 = 8021, 8022
    init.user_details[u1] = init._default_user()
    # Even if subscriber/VIP, scams are 100% blocked
    init.user_details[u1]["subscription_expires"] = time.time() + 86400
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100

    mock_update = MagicMock()
    mock_update.effective_user.id = u1
    mock_update.message.text = "Join my free stars bot send stars get double!"
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
    mock_context.bot.send_message.assert_not_called()
    mock_update.message.reply_text.assert_called_once()
    assert "Message blocked" in mock_update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_media_spoiler_toggle_in_edit_handler():
    from handlers.edit import handle_edit_selection
    from commands.profile import _profile_keyboard
    u = 8023
    init.user_details[u] = init._default_user()
    assert init.user_details[u].get("media_spoiler", True) is True

    # Check keyboard button text
    kb = _profile_keyboard(u)
    buttons = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Media Shield: ON 🟢" in b for b in buttons)

    # Trigger toggle callback
    mock_update = MagicMock()
    mock_query = MagicMock()
    mock_query.from_user.id = u
    mock_query.data = "edit|toggle_spoiler"
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    mock_update.callback_query = mock_query

    mock_context = MagicMock()
    mock_context.bot.get_chat = AsyncMock(return_value=MagicMock(full_name="Tester", username="tester"))
    await handle_edit_selection(mock_update, mock_context)

    # After toggle, setting is False
    assert init.user_details[u]["media_spoiler"] is False
    assert u in init.dirty_users

    # Keyboard reflects OFF state
    kb2 = _profile_keyboard(u)
    buttons2 = [btn.text for row in kb2.inline_keyboard for btn in row]
    assert any("Media Shield: OFF ⚪" in b for b in buttons2)


@pytest.mark.asyncio
async def test_short_message_handle_blocked_and_long_message_masked():
    u1, u2 = 8031, 8032
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=9001))
    mock_context.bot.send_chat_action = AsyncMock()

    # 1. Short message handle drop (< 6 words): "super_storm5" -> BLOCKED
    mock_update1 = MagicMock()
    mock_update1.effective_user.id = u1
    mock_update1.message.text = "super_storm5"
    mock_update1.message.caption = None
    mock_update1.message.entities = None
    mock_update1.message.caption_entities = None
    mock_update1.message.photo = None
    mock_update1.message.video = None
    mock_update1.message.voice = None
    mock_update1.message.video_note = None
    mock_update1.message.sticker = None
    mock_update1.message.animation = None
    mock_update1.message.document = None
    mock_update1.message.audio = None
    mock_update1.message.dice = None
    mock_update1.message.reply_to_message = None
    mock_update1.message.reply_text = AsyncMock()

    await relay_message(mock_update1, mock_context)
    mock_context.bot.send_message.assert_not_called()
    mock_update1.message.reply_text.assert_called_once()
    assert "Links and usernames cannot be shared" in mock_update1.message.reply_text.call_args[1]["text"]

    # 2. Long message with handle (>= 6 words): "imagine asking to add your acc with the tag that_cool_guy_67 in big 2026"
    # -> MASKED and RELAYED (joke preserved, handle masked)
    mock_context.bot.send_message.reset_mock()
    mock_update2 = MagicMock()
    mock_update2.effective_user.id = u1
    mock_update2.message.text = "imagine asking to add your acc with the tag that_cool_guy_67 in big 2026"
    mock_update2.message.caption = None
    mock_update2.message.entities = None
    mock_update2.message.caption_entities = None
    mock_update2.message.photo = None
    mock_update2.message.video = None
    mock_update2.message.voice = None
    mock_update2.message.video_note = None
    mock_update2.message.sticker = None
    mock_update2.message.animation = None
    mock_update2.message.document = None
    mock_update2.message.audio = None
    mock_update2.message.dice = None
    mock_update2.message.reply_to_message = None
    mock_update2.message.reply_text = AsyncMock()

    await relay_message(mock_update2, mock_context)
    mock_context.bot.send_message.assert_called_once()
    sent_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "[hidden 🔒]" in sent_text
    assert "that_cool_guy_67" not in sent_text
    assert "imagine asking to add your acc with the tag" in sent_text

    # 3. Conversational normal text: "I'm js testing something, don't mind me"
    # -> Relayed completely clean and untouched
    mock_context.bot.send_message.reset_mock()
    mock_update3 = MagicMock()
    mock_update3.effective_user.id = u1
    mock_update3.message.text = "I'm js testing something, don't mind me"
    mock_update3.message.caption = None
    mock_update3.message.entities = None
    mock_update3.message.caption_entities = None
    mock_update3.message.photo = None
    mock_update3.message.video = None
    mock_update3.message.voice = None
    mock_update3.message.video_note = None
    mock_update3.message.sticker = None
    mock_update3.message.animation = None
    mock_update3.message.document = None
    mock_update3.message.audio = None
    mock_update3.message.dice = None
    mock_update3.message.reply_to_message = None
    mock_update3.message.reply_text = AsyncMock()

    await relay_message(mock_update3, mock_context)
    mock_context.bot.send_message.assert_called_once()
    assert mock_context.bot.send_message.call_args[1]["text"] == "I'm js testing something, don't mind me"


@pytest.mark.asyncio
async def test_bot_username_restrictions_and_safe_words():
    u1, u2 = 8041, 8042
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.session_start_times[u1] = time.time() - 100

    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=9002))
    mock_context.bot.send_chat_action = AsyncMock()

    # 1. Standalone / Short message with bot handle (< 6 words): "AnonChatZoneBot" -> BLOCKED
    mock_update1 = MagicMock()
    mock_update1.effective_user.id = u1
    mock_update1.message.text = "AnonChatZoneBot"
    mock_update1.message.caption = None
    mock_update1.message.entities = None
    mock_update1.message.caption_entities = None
    mock_update1.message.photo = None
    mock_update1.message.video = None
    mock_update1.message.voice = None
    mock_update1.message.video_note = None
    mock_update1.message.sticker = None
    mock_update1.message.animation = None
    mock_update1.message.document = None
    mock_update1.message.audio = None
    mock_update1.message.dice = None
    mock_update1.message.reply_to_message = None
    mock_update1.message.reply_text = AsyncMock()

    await relay_message(mock_update1, mock_context)
    mock_context.bot.send_message.assert_not_called()
    mock_update1.message.reply_text.assert_called_once()
    assert "Links and usernames cannot be shared" in mock_update1.message.reply_text.call_args[1]["text"]

    # 2. Long message with bot handle (>= 6 words): "someone told me AnonChatZoneBot has free stars in big 2026"
    # -> MASKED in-place to "[hidden 🔒]" and relayed
    mock_context.bot.send_message.reset_mock()
    mock_update2 = MagicMock()
    mock_update2.effective_user.id = u1
    mock_update2.message.text = "someone told me AnonChatZoneBot has free stars in big 2026"
    mock_update2.message.caption = None
    mock_update2.message.entities = None
    mock_update2.message.caption_entities = None
    mock_update2.message.photo = None
    mock_update2.message.video = None
    mock_update2.message.voice = None
    mock_update2.message.video_note = None
    mock_update2.message.sticker = None
    mock_update2.message.animation = None
    mock_update2.message.document = None
    mock_update2.message.audio = None
    mock_update2.message.dice = None
    mock_update2.message.reply_to_message = None
    mock_update2.message.reply_text = AsyncMock()

    await relay_message(mock_update2, mock_context)
    mock_context.bot.send_message.assert_called_once()
    sent_text = mock_context.bot.send_message.call_args[1]["text"]
    assert "[hidden 🔒]" in sent_text
    assert "AnonChatZoneBot" not in sent_text
    assert "someone told me [hidden 🔒] has free stars in big 2026" == sent_text

    # 3. Whitelisted English words ending in 'bot' ("robot", "chatbot", "bot") -> Allowed clean & untouched
    mock_context.bot.send_message.reset_mock()
    mock_update3 = MagicMock()
    mock_update3.effective_user.id = u1
    mock_update3.message.text = "are you a real bot or a chatbot?"
    mock_update3.message.caption = None
    mock_update3.message.entities = None
    mock_update3.message.caption_entities = None
    mock_update3.message.photo = None
    mock_update3.message.video = None
    mock_update3.message.voice = None
    mock_update3.message.video_note = None
    mock_update3.message.sticker = None
    mock_update3.message.animation = None
    mock_update3.message.document = None
    mock_update3.message.audio = None
    mock_update3.message.dice = None
    mock_update3.message.reply_to_message = None
    mock_update3.message.reply_text = AsyncMock()

    await relay_message(mock_update3, mock_context)
    mock_context.bot.send_message.assert_called_once()
    assert mock_context.bot.send_message.call_args[1]["text"] == "are you a real bot or a chatbot?"

    # 4. Another safe word ("robot") -> Allowed
    mock_context.bot.send_message.reset_mock()
    mock_update4 = MagicMock()
    mock_update4.effective_user.id = u1
    mock_update4.message.text = "I love this robot"
    mock_update4.message.caption = None
    mock_update4.message.entities = None
    mock_update4.message.caption_entities = None
    mock_update4.message.photo = None
    mock_update4.message.video = None
    mock_update4.message.voice = None
    mock_update4.message.video_note = None
    mock_update4.message.sticker = None
    mock_update4.message.animation = None
    mock_update4.message.document = None
    mock_update4.message.audio = None
    mock_update4.message.dice = None
    mock_update4.message.reply_to_message = None
    mock_update4.message.reply_text = AsyncMock()

    await relay_message(mock_update4, mock_context)
    mock_context.bot.send_message.assert_called_once()
    assert mock_context.bot.send_message.call_args[1]["text"] == "I love this robot"


@pytest.mark.asyncio
async def test_telegram_handle_live_verification_and_caching():
    from security import verify_telegram_handle
    from saveNload import get_cached_telegram_handle
    from telegram.error import BadRequest

    mock_bot = MagicMock()
    mock_chat = MagicMock(type="bot")
    mock_bot.get_chat = AsyncMock(return_value=mock_chat)

    # 1. Valid Telegram handle verification
    handle = "TestVerifiedZoneBot"
    is_valid = await verify_telegram_handle(handle, bot=mock_bot)
    assert is_valid is True
    mock_bot.get_chat.assert_called_once_with(f"@{handle}")

    # Cached in memory & DB
    cached = await get_cached_telegram_handle(handle)
    assert cached == (True, "bot")

    # Second call uses cache (get_chat not called again)
    mock_bot.get_chat.reset_mock()
    is_valid_second = await verify_telegram_handle(handle, bot=mock_bot)
    assert is_valid_second is True
    mock_bot.get_chat.assert_not_called()

    # 2. Non-existent Telegram handle (BadRequest "Chat not found")
    non_existent = "DefinitelyFakeNonExistent1234Bot"
    mock_bot.get_chat = AsyncMock(side_effect=BadRequest("Chat not found"))

    is_valid_fake = await verify_telegram_handle(non_existent, bot=mock_bot)
    assert is_valid_fake is False

    cached_fake = await get_cached_telegram_handle(non_existent)
    assert cached_fake == (False, "")

    # Second call uses cache
    mock_bot.get_chat.reset_mock()
    is_valid_fake_second = await verify_telegram_handle(non_existent, bot=mock_bot)
    assert is_valid_fake_second is False
    mock_bot.get_chat.assert_not_called()

    # 3. Simulate bot reboot: memory cleared, pre-warmed from DB via load_all_verified_handles_db
    from saveNload import _in_memory_verified_handles, load_all_verified_handles_db
    _in_memory_verified_handles.clear()
    assert handle.lower() not in _in_memory_verified_handles

    mock_cur = MagicMock()
    mock_cur.fetchall = AsyncMock(return_value=[("rebootbot", True, "bot")])
    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock(return_value=mock_cur)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=mock_conn)

    monkeypatch = pytest.MonkeyPatch()
    import saveNload
    monkeypatch.setattr(saveNload, "is_pool_ready", lambda: True)
    monkeypatch.setattr(saveNload, "get_pool", lambda: mock_pool)
    try:
        loaded_count = await load_all_verified_handles_db()
        assert loaded_count == 1
        assert _in_memory_verified_handles["rebootbot"] == (True, "bot")
    finally:
        monkeypatch.undo()




