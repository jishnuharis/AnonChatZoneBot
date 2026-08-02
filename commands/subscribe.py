from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import SUBSCRIBE_INTRO_TEXT, SUBSCRIBE_INVOICE_TITLE, SUBSCRIBE_INVOICE_DESCRIPTION
import subscription

import init


def _tier_keyboard():
    rows = []
    for key in subscription.TIER_ORDER:
        tier = subscription.TIERS[key]
        rows.append([InlineKeyboardButton(
            f"{tier['label']} — {tier['stars']} ⭐ (+{tier['limit_bonus']} daily credits, unlimited photos)",
            callback_data=f"sub|{key}",
        )])
    return InlineKeyboardMarkup(rows)


@check_user_profile
async def show_subscribe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = SUBSCRIBE_INTRO_TEXT.format(status=subscription.status_text(user_id))
    await safe_tele_func_call(
        update.message.reply_text, text=text, reply_markup=_tier_keyboard(), parse_mode="HTML"
    )


async def handle_tier_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fires a Telegram Stars invoice for the chosen tier. Stars payments use
    currency='XTR' with an empty provider_token - Telegram handles the whole
    payment UI natively, there's no external payment provider involved."""
    query = update.callback_query
    await query.answer()
    tier_key = query.data.split("|")[1]
    tier = subscription.TIERS.get(tier_key)
    if not tier:
        return

    user_id = query.from_user.id
    limit = subscription.FREE_DAILY_CREDIT_LIMIT + tier["limit_bonus"]

    await safe_tele_func_call(
        context.bot.send_invoice,
        chat_id=user_id,
        title=SUBSCRIBE_INVOICE_TITLE.format(label=tier["label"]),
        description=SUBSCRIBE_INVOICE_DESCRIPTION.format(
            label=tier["label"], limit=limit, points=tier["bonus_points"]
        ),
        payload=f"sub|{tier_key}",
        provider_token="",  # Empty for Telegram Stars - no external payment provider
        currency="XTR",
        prices=[LabeledPrice(tier["label"], tier["stars"])],  # For XTR, amount = star count directly (no cent multiplier)
    )
