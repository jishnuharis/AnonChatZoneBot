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
            f"{tier['label']} — {tier['stars']} ⭐ (+{tier['limit_bonus']} daily credits, unlimited calls & media)",
            callback_data=f"sub|{key}",
        )])
    return InlineKeyboardMarkup(rows)


@check_user_profile
async def show_subscribe_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from group_helper import is_group_chat
    user_id = update.effective_user.id
    text = SUBSCRIBE_INTRO_TEXT.format(status=subscription.status_text(user_id))

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
                text=f"📩 <b>{user_tag}</b>, <i>I have sent the VIP subscription tiers to your private DM!</i>",
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Start Bot in DM", url=f"https://t.me/{bot_username}?start=subscribe")]])
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>{user_tag}</b>, <i>please start the bot in private DM first so I can send the VIP tiers!</i>",
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

    if tier_key == "upgrade_prompt":
        user_id = query.from_user.id
        text = SUBSCRIBE_INTRO_TEXT.format(status=subscription.status_text(user_id))
        await safe_tele_func_call(query.edit_message_text, text=text, reply_markup=_tier_keyboard(), parse_mode="HTML")
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
