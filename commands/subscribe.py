import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from message import (
    SUBSCRIBE_INTRO_TEXT,
    SUBSCRIBE_COMPARE_TEXT,
    SUBSCRIBE_INVOICE_TITLE,
    SUBSCRIBE_INVOICE_DESCRIPTION,
    SUBSCRIBE_GROUP_DM_SENT_TEXT,
    SUBSCRIBE_GROUP_START_DM_TEXT,
)
import subscription

import init


def get_admin_contact_url() -> str:
    """Returns the admin contact URL for direct purchases."""
    if os.getenv("ADMIN_CONTACT_URL"):
        return os.getenv("ADMIN_CONTACT_URL")
    admin_user = os.getenv("ADMIN_USERNAME")
    if admin_user:
        clean = admin_user.lstrip("@").strip()
        return f"https://t.me/{clean}"
    return "https://t.me/channelofchatzone"


def _tier_keyboard():
    admin_url = get_admin_contact_url()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 1 Day (25 ⭐)", callback_data="sub|daily"),
            InlineKeyboardButton("✨ 1 Week (125 ⭐)", callback_data="sub|weekly"),
        ],
        [
            InlineKeyboardButton("🌙 1 Month (450 ⭐)", callback_data="sub|monthly"),
            InlineKeyboardButton("👑 1 Year (4,500 ⭐)", callback_data="sub|yearly"),
        ],
        [
            InlineKeyboardButton("📋 Compare All Tier Perks", callback_data="sub|compare"),
        ],
        [
            InlineKeyboardButton("💎 Buy VIP via Admin (Direct)", url=admin_url),
        ],
    ])


def _compare_keyboard():
    admin_url = get_admin_contact_url()
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ 1 Day (25 ⭐)", callback_data="sub|daily"),
            InlineKeyboardButton("✨ 1 Week (125 ⭐)", callback_data="sub|weekly"),
        ],
        [
            InlineKeyboardButton("🌙 1 Month (450 ⭐)", callback_data="sub|monthly"),
            InlineKeyboardButton("👑 1 Year (4,500 ⭐)", callback_data="sub|yearly"),
        ],
        [
            InlineKeyboardButton("⬅️ Back to VIP Plans", callback_data="sub|back"),
            InlineKeyboardButton("💎 Buy (Admin)", url=admin_url),
        ],
    ])


@check_user_profile
async def show_subscribe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from group_helper import is_group_chat
    user_id = update.effective_user.id
    admin_url = get_admin_contact_url()
    text = SUBSCRIBE_INTRO_TEXT.format(
        status=subscription.status_text(user_id),
        admin_url=admin_url,
    )

    if is_group_chat(update):
        bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
        user_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        dm_sent = await safe_tele_func_call(
            context.bot.send_message, chat_id=user_id, text=text, reply_markup=_tier_keyboard(), parse_mode="HTML"
        )
        if dm_sent:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("⭐ View VIP Perks", url=f"https://t.me/{bot_username}?start=subscribe")]])
            await safe_tele_func_call(
                update.message.reply_text,
                text=SUBSCRIBE_GROUP_DM_SENT_TEXT.format(user_tag=user_tag),
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Start Bot in DM", url=f"https://t.me/{bot_username}?start=subscribe")]])
            await safe_tele_func_call(
                update.message.reply_text,
                text=SUBSCRIBE_GROUP_START_DM_TEXT.format(user_tag=user_tag),
                reply_markup=kb,
                parse_mode="HTML"
            )
        return

    await safe_tele_func_call(
        update.message.reply_text, text=text, reply_markup=_tier_keyboard(), parse_mode="HTML"
    )


async def handle_tier_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tier_key = query.data.split("|")[1]
    admin_url = get_admin_contact_url()

    if tier_key in ("upgrade_prompt", "back"):
        user_id = query.from_user.id
        text = SUBSCRIBE_INTRO_TEXT.format(
            status=subscription.status_text(user_id),
            admin_url=admin_url,
        )
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=_tier_keyboard(), parse_mode="HTML")
        return

    if tier_key == "compare":
        text = SUBSCRIBE_COMPARE_TEXT.format(admin_url=admin_url)
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=_compare_keyboard(), parse_mode="HTML")
        return

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
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(tier["label"], tier["stars"])],
    )
