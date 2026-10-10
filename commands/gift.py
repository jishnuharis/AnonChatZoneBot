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


def _gift_keyboard(target_id: int = None, group_id: int = None) -> InlineKeyboardMarkup:
    """Builds inline keyboard for the gift catalog."""
    rows = []
    suffix = f"|{target_id}|{group_id}" if target_id and group_id else ""
    for g_id, gift in GIFTS.items():
        vip_tag = " + 1d VIP" if gift.get("vip_days") else ""
        label = f"{gift['emoji']} {gift['name']} — {gift['stars']} ⭐ (+{gift['points_reward']} pts{vip_tag})"
        rows.append([InlineKeyboardButton(label, callback_data=f"gift|{g_id}{suffix}")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"gift|cancel{suffix}")])
    return InlineKeyboardMarkup(rows)


@check_user_profile
async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /gift command in chat or group."""
    from group_helper import is_group_chat, resolve_target, get_group_redirect_keyboard
    user_id = update.effective_user.id

    if is_group_chat(update):
        # 1. Resolve target
        target_res = await resolve_target(update, context)
        if not target_res:
            await safe_tele_func_call(
                update.message.reply_text,
                text="ℹ️ <i>Reply to a user's message with</i> <code>/gift</code> <i>or type</i> <code>/gift @username</code> <i>to send them a gift!</i>",
                parse_mode="HTML"
            )
            return

        target_id, target_name = target_res

        # 2. Check sender presence first
        if user_id not in init.user_details:
            await init.ensure_user_loaded(user_id)
        sender_data = init.user_details.get(user_id)
        if not sender_data or not all([sender_data.get("gender"), sender_data.get("age"), sender_data.get("country")]):
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text="⚠️ <b>You haven't registered with the bot yet!</b>\n\nStart the bot first in private chat to use this feature.",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
            return

        # 3. Check target presence
        if not target_id:
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>Target user ({target_name}) has not registered with our bot yet.</b>",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
            return

        if target_id == user_id:
            await safe_tele_func_call(
                update.message.reply_text,
                text="😅 <i>You cannot gift yourself!</i>",
                parse_mode="HTML"
            )
            return

        if target_id not in init.user_details:
            await init.ensure_user_loaded(target_id)
        target_data = init.user_details.get(target_id)
        if not target_data or not all([target_data.get("gender"), target_data.get("age"), target_data.get("country")]):
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>Target user ({target_name}) has not registered with our bot yet.</b>",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
            return

        # 4. Dispatch gift catalog in private DM to sender
        catalog_text = (
            f"🎁 <b>Send a Gift to {target_name}!</b> ⭐\n\n"
            f"Choose a Telegram Stars gift below to reward them with bonus points and VIP perks:\n\n"
            f"☕ <b>Warm Coffee</b> — 15 ⭐ <i>(+50 Points)</i>\n"
            f"🌹 <b>Red Rose</b> — 25 ⭐ <i>(+100 Points)</i>\n"
            f"🍕 <b>Hot Pizza</b> — 50 ⭐ <i>(+250 Points)</i>\n"
            f"👑 <b>Royal Crown</b> — 100 ⭐ <i>(+500 Points & 1 Day VIP Access!)</i>\n\n"
            f"<i>Select a gift:</i>"
        )
        dm_sent = await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user_id,
            text=catalog_text,
            reply_markup=_gift_keyboard(target_id=target_id, group_id=update.effective_chat.id),
            parse_mode="HTML"
        )

        sender_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        if dm_sent:
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"🎁 <b>{sender_tag} is preparing a gift for {target_name} in their DMs!</b>",
                parse_mode="HTML"
            )
        else:
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>{sender_tag}</b>, <i>please start the bot in private DM first so we can deliver the gift options!</i>",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
        return

    if not is_in_chat(user_id):
        await safe_tele_func_call(
            update.message.reply_text,
            text="❌ <i>You can only send gifts during an active chat! Use</i> /next <i>to find someone.</i>",
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
    gift = GIFTS.get(gift_id)
    if not gift:
        return

    # Check if target_id & group_id passed in callback data (from group gift)
    if len(parts) >= 4:
        target_id = int(parts[2])
        group_id = int(parts[3])
        payload = f"gift|{gift_id}|{target_id}|{group_id}"
    else:
        partner_id = get_partner(user_id)
        if not partner_id:
            await safe_tele_func_call(
                query.edit_message_text,
                text="❌ <i>Your chat partner has disconnected. Cannot send gift.</i>",
                parse_mode="HTML",
            )
            return
        payload = f"gift|{gift_id}|{partner_id}"

    await safe_tele_func_call(
        context.bot.send_invoice,
        chat_id=user_id,
        title=f"Gift: {gift['emoji']} {gift['name']}",
        description=gift["desc"],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(f"{gift['emoji']} {gift['name']}", gift["stars"])],
    )
