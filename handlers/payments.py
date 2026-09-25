import time

from telegram import Update
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from message import SUBSCRIBE_PAYMENT_SUCCESS_TEXT
import subscription

import init


async def handle_pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    payload = query.invoice_payload

    if payload.startswith("sub|"):
        tier_key = payload.split("|")[-1]
        if tier_key in subscription.TIERS:
            await safe_tele_func_call(query.answer, ok=True)
        else:
            await safe_tele_func_call(query.answer, ok=False, error_message="This plan is no longer available. Please try /subscribe again.")
    elif payload.startswith("gift|"):
        from commands.gift import GIFTS
        parts = payload.split("|")
        gift_id = parts[1] if len(parts) >= 2 else None
        if gift_id in GIFTS:
            await safe_tele_func_call(query.answer, ok=True)
        else:
            await safe_tele_func_call(query.answer, ok=False, error_message="This gift is no longer available. Please try /gift again.")
    else:
        await safe_tele_func_call(query.answer, ok=False, error_message="Invalid payment request.")


async def handle_successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user_id = update.effective_user.id
    payload = payment.invoice_payload

    if payload.startswith("sub|"):
        tier_key = payload.split("|", 1)[1]
        if tier_key not in subscription.TIERS:
            return

        tier = subscription.TIERS[tier_key]
        new_expiry = subscription.grant_subscription(user_id, tier_key, source="purchase")

        from saveNload import add_subscription_db, record_payment_transaction_db
        await add_subscription_db(user_id, tier_key, tier["duration_days"], source="purchase")
        await record_payment_transaction_db(user_id, tier_key, tier["stars"], charge_id=payment.telegram_payment_charge_id)

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
    elif payload.startswith("gift|"):
        from commands.gift import GIFTS
        parts = payload.split("|")
        if len(parts) < 3:
            return
        gift_id = parts[1]
        try:
            partner_id = int(parts[2])
        except ValueError:
            return

        gift = GIFTS.get(gift_id)
        if not gift:
            return

        if partner_id not in init.user_details:
            await init.ensure_user_loaded(partner_id)
        p_details = init.user_details.setdefault(partner_id, init._default_user())

        p_details["points"] = p_details.get("points", 0) + gift["points_reward"]

        vip_reward_text = ""
        if gift.get("vip_days", 0) > 0:
            vip_days = gift["vip_days"]
            from subscription import grant_vip_days
            grant_vip_days(partner_id, days=vip_days, tier_key="daily", source="gift")
            try:
                from saveNload import add_subscription_db
                await add_subscription_db(partner_id, tier="daily", duration_days=vip_days, source="gift")
            except Exception as e:
                pass
            vip_reward_text = f" + <b>{vip_days} Day VIP Access</b>"

        init.dirty_users.add(partner_id)

        from saveNload import record_payment_transaction_db
        await record_payment_transaction_db(
            user_id, f"gift_{gift_id}", gift["stars"], charge_id=payment.telegram_payment_charge_id
        )

        await safe_tele_func_call(
            update.message.reply_text,
            text=(
                f"🎁 <b>Gift Delivered!</b>\n\n"
                f"You sent a <b>{gift['emoji']} {gift['name']}</b> to your chat partner! "
                f"Thank you for spreading joy in Chat Zone! ⭐"
            ),
            parse_mode="HTML",
        )

        partner_notice = (
            f"🎉 <b>WOW! Your chat partner sent you a Gift!</b> 🎁\n\n"
            f"<blockquote>\n"
            f"{gift['emoji']} <b>{gift['name']}</b>\n"
            f"✨ <i>Reward received:</i> <b>+{gift['points_reward']} Points</b>{vip_reward_text}\n"
            f"</blockquote>\n\n"
            f"<i>Say thank you to your partner in chat!</i> ❤️"
        )
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=partner_id,
            text=partner_notice,
            parse_mode="HTML",
        )
