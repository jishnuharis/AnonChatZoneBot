"""
Sponsors and Promotions Service for AnonChatZoneBot.

Supports data-driven campaigns, impressions/click tracking, frequency control,
and non-intrusive post-chat display.
"""

import time
import random
import logging
from typing import Optional, Dict, Any, List

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from saveNload import (
    get_active_promotions_db,
    increment_promo_impression_db,
    increment_promo_click_db,
    add_promotion_db,
)

logger = logging.getLogger(__name__)

# Cooldown between promotions per user (minimum 10 minutes between promo displays)
_user_last_promo_time: Dict[int, float] = {}
PROMO_COOLDOWN_SECONDS = 600
PROMO_CHANCE = 0.25  # 25% chance after chat completion


async def maybe_show_promotion(bot, user_id: int) -> bool:
    """
    Checks eligibility and displays an active sponsor campaign post-chat.
    Respects cooldowns and frequency rules without disrupting conversations.
    """
    now = time.time()
    last_shown = _user_last_promo_time.get(user_id, 0)
    if now - last_shown < PROMO_COOLDOWN_SECONDS:
        return False

    if random.random() > PROMO_CHANCE:
        return False

    try:
        campaigns = await get_active_promotions_db()
        if not campaigns:
            return False

        # Pick top priority campaign
        promo = campaigns[0]
        promo_id = promo["id"]

        keyboard = None
        if promo.get("button_text") and promo.get("button_url"):
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(promo["button_text"], url=promo["button_url"])
            ]])

        text = f"📢 <b>Sponsored: {promo['sponsor_name']}</b>\n\n{promo['message_text']}"

        msg = await safe_tele_func_call(
            bot.send_message,
            chat_id=user_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )

        if msg:
            _user_last_promo_time[user_id] = now
            await increment_promo_impression_db(promo_id)
            return True
    except Exception as e:
        logger.debug(f"Notice in maybe_show_promotion: {e}")

    return False


async def record_click(promo_id: int):
    """Records a click on a promotion button."""
    try:
        await increment_promo_click_db(promo_id)
    except Exception as e:
        logger.error(f"Failed to record promo click for {promo_id}: {e}")
