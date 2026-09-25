"""
Automated Sponsors & Promotions System Tests.
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock

from promotions.service import maybe_show_promotion, _user_last_promo_time, PROMO_COOLDOWN_SECONDS


@pytest.mark.asyncio
async def test_promotion_cooldown(monkeypatch):
    user_id = 999
    # Simulate promotion shown just now
    _user_last_promo_time[user_id] = time.time()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()

    # Second check immediately after should return False due to cooldown
    shown = await maybe_show_promotion(mock_bot, user_id)
    assert shown is False
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_promotion_display_with_active_campaign(monkeypatch):
    user_id = 888
    _user_last_promo_time[user_id] = 0.0 # reset cooldown

    # Mock active campaign
    async def mock_get_promos():
        return [{
            "id": 1,
            "title": "Special Deal",
            "sponsor_name": "Acme Corp",
            "message_text": "Check out our services!",
            "button_text": "Visit",
            "button_url": "https://example.com"
        }]

    async def mock_incr(pid):
        pass

    monkeypatch.setattr("promotions.service.get_active_promotions_db", mock_get_promos)
    monkeypatch.setattr("promotions.service.increment_promo_impression_db", mock_incr)
    monkeypatch.setattr("promotions.service.PROMO_CHANCE", 1.0) # 100% chance for test

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=MagicMock())

    shown = await maybe_show_promotion(mock_bot, user_id)
    assert shown is True
    mock_bot.send_message.assert_called_once()
    assert "Acme Corp" in mock_bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_promotion_display_with_photo_campaign(monkeypatch):
    """Verify that campaigns with photos use send_photo instead of send_message."""
    user_id = 777
    _user_last_promo_time[user_id] = 0.0

    async def mock_get_promos():
        return [{
            "id": 2,
            "title": "Photo Deal",
            "sponsor_name": "Visual Brand",
            "message_text": "Check out our visual products!",
            "button_text": "Shop Now",
            "button_url": "https://example.com/shop",
            "photo_url": "https://example.com/banner.jpg"
        }]

    async def mock_incr(pid):
        pass

    monkeypatch.setattr("promotions.service.get_active_promotions_db", mock_get_promos)
    monkeypatch.setattr("promotions.service.increment_promo_impression_db", mock_incr)
    monkeypatch.setattr("promotions.service.PROMO_CHANCE", 1.0)

    mock_bot = MagicMock()
    mock_bot.send_photo = AsyncMock(return_value=MagicMock())
    mock_bot.send_message = AsyncMock()

    shown = await maybe_show_promotion(mock_bot, user_id)
    assert shown is True
    mock_bot.send_photo.assert_called_once()
    photo_args = mock_bot.send_photo.call_args[1]
    assert photo_args["photo"] == "https://example.com/banner.jpg"
    assert "Visual Brand" in photo_args["caption"]
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_campaign_create_with_photo(monkeypatch):
    """Verify /campaign create supports photos via pipes and message attachments."""
    from commands.admin_commands import campaign_command
    import init

    admin_id = 99991
    init.ADMIN_IDS.add(admin_id)

    mock_add = AsyncMock(return_value=105)
    monkeypatch.setattr("commands.admin_commands.add_promotion_db", mock_add)

    # 1. Pipe syntax with photo URL
    update = MagicMock()
    update.effective_user.id = admin_id
    update.message.text = "/campaign create Acme | Big Sale | Get 50% off | Buy | https://sale.com | https://sale.com/img.jpg"
    update.message.photo = None
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = update.message.text.split()[1:]

    await campaign_command(update, context)
    mock_add.assert_called_once()
    add_kwargs = mock_add.call_args[1]
    assert add_kwargs["photo_url"] == "https://sale.com/img.jpg"
    assert "with photo" in update.message.reply_text.call_args[0][0]

    # 2. Attached photo message
    mock_add.reset_mock()
    photo_obj = MagicMock()
    photo_obj.file_id = "file_id_promo_photo_123"
    update.message.photo = [photo_obj]
    update.message.text = "/campaign create Acme2 | Sale 2 | Check it out"
    context.args = update.message.text.split()[1:]

    await campaign_command(update, context)
    mock_add.assert_called_once()
    assert mock_add.call_args[1]["photo_url"] == "file_id_promo_photo_123"

