"""
Telegram Stars In-Chat Gifting (/gift) for AnonChatZoneBot.

Allows chat partners to send real Telegram Stars gifts:
- ☕ Warm Coffee (15 Stars -> +50 pts)
- 🌹 Red Rose (25 Stars -> +100 pts)
- 🍕 Hot Pizza (50 Stars -> +250 pts)
- 👑 Royal Crown (100 Stars -> +500 pts + 1d VIP)
"""

import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

import init
from session_manager import is_in_chat, get_partner
from handlers.setup import check_user_profile
from security import safe_tele_func_call

logger = logging.getLogger(__name__)

GIFTS: Dict[str, Dict[str, Any]] = {
    "coffee": {
        "id": "coffee",
        "name": "Warm Coffee",
        "emoji": "☕",
        "stars": 15,
        "points_reward": 50,
        "vip_days": 0,
        "desc": "Send a warm cup of coffee (+50 points) to brighten their day!",
    },
    "rose": {
        "id": "rose",
        "name": "Red Rose",
        "emoji": "🌹",
        "stars": 25,
        "points_reward": 100,
        "vip_days": 0,
        "desc": "Send an anonymous sweet red rose (+100 points) to your partner!",
    },
    "pizza": {
        "id": "pizza",
        "name": "Hot Pizza",
        "emoji": "🍕",
        "stars": 50,
        "points_reward": 250,
        "vip_days": 0,
        "desc": "Treat your partner to a hot slice of pizza (+250 points)!",
    },
    "crown": {
        "id": "crown",
        "name": "Royal Crown",
        "emoji": "👑",
        "stars": 100,
        "points_reward": 500,
        "vip_days": 1,
        "desc": "Crown your partner as royalty! (+500 points & 1 Day VIP Access)!",
    },
}


def _gift_keyboard() -> InlineKeyboardMarkup:
    """Builds inline keyboard for the gift catalog."""
    rows = []
    for g_id, gift in GIFTS.items():
        vip_tag = " + 1d VIP" if gift.get("vip_days") else ""
        label = f"{gift['emoji']} {gift['name']} — {gift['stars']} ⭐ (+{gift['points_reward']} pts{vip_tag})"
        rows.append([InlineKeyboardButton(label, callback_data=f"gift|{g_id}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="gift|cancel")])
    return InlineKeyboardMarkup(rows)


@check_user_profile
async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /gift command in chat."""
    user_id = update.effective_user.id
    if not is_in_chat(user_id):
        await safe_tele_func_call(
            update.message.reply_text,
            text="❌ <i>You can only send gifts during an active chat! Use /next to find someone.</i>",
            parse_mode="HTML"
        )
        return

    text = (
        "🎁 <b>Send an Anonymous Gift to your Chat Partner!</b> ⭐\n\n"
        "Surprise your partner with a Telegram Stars gift! All gifts instantly reward them with points and VIP perks:\n\n"
        "☕ <b>Warm Coffee</b> — 15 ⭐ <i>(+50 Points)</i>\n"
        "🌹 <b>Red Rose</b> — 25 ⭐ <i>(+100 Points)</i>\n"
        "🍕 <b>Hot Pizza</b> — 50 ⭐ <i>(+250 Points)</i>\n"
        "👑 <b>Royal Crown</b> — 100 ⭐ <i>(+500 Points & 1 Day VIP Access!)</i>\n\n"
        "<i>Choose a gift below:</i>"
    )

    await safe_tele_func_call(
        update.message.reply_text,
        text=text,
        reply_markup=_gift_keyboard(),
        parse_mode="HTML",
    )


async def handle_gift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes gift selection and issues Telegram Stars invoice."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split("|")
    gift_id = parts[1] if len(parts) > 1 else ""

    if gift_id == "cancel":
        await safe_tele_func_call(
            query.edit_message_text,
            text="❌ <i>Gift cancelled.</i>",
            parse_mode="HTML",
        )
        return

    user_id = update.effective_user.id
    partner_id = get_partner(user_id)
    if not partner_id:
        await safe_tele_func_call(
            query.edit_message_text,
            text="❌ <i>Your chat partner has disconnected. Cannot send gift.</i>",
            parse_mode="HTML",
        )
        return

    gift = GIFTS.get(gift_id)
    if not gift:
        return

    await safe_tele_func_call(
        context.bot.send_invoice,
        chat_id=user_id,
        title=f"Gift: {gift['emoji']} {gift['name']}",
        description=gift["desc"],
        payload=f"gift|{gift_id}|{partner_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(f"{gift['emoji']} {gift['name']}", gift["stars"])],
    )
