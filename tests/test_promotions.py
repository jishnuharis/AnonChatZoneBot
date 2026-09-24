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
