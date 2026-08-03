import time

from telegram import Update
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from message import SUBSCRIBE_PAYMENT_SUCCESS_TEXT
import subscription

import init


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    tier_key = query.invoice_payload.split("|")[-1] if query.invoice_payload.startswith("sub|") else None
    if tier_key in subscription.TIERS:
        await safe_tele_func_call(query.answer, ok=True)
    else:
        await safe_tele_func_call(query.answer, ok=False, error_message="This plan is no longer available. Please try /subscribe again.")


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload

    if not payload.startswith("sub|"):
        return
    tier_key = payload.split("|", 1)[1]
    if tier_key not in subscription.TIERS:
        return

    tier = subscription.TIERS[tier_key]
    new_expiry = subscription.grant_subscription(user_id, tier_key, source="purchase")

    await safe_tele_func_call(
        update.message.reply_text,
        text=SUBSCRIBE_PAYMENT_SUCCESS_TEXT.format(
            label=tier["label"],
            expires=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(new_expiry)),
            points=tier["bonus_points"],
            limit=subscription.daily_credit_limit(user_id),
        ),
        parse_mode="HTML",
    )
