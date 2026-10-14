"""
Two-Way Message Eraser (/prune) for AnonChatZoneBot.
Deletes the replied message on BOTH sides (sender's chat and partner's chat).
Exclusive perk for all VIP subscribers (Daily, Weekly, Monthly, Yearly).
"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call
from subscription import is_subscribed
from group_helper import is_group_chat

logger = logging.getLogger(__name__)

PRUNE_NOT_IN_CHAT = "⚠️ <b>You are not currently in an active chat.</b>\n\nUse /find to connect with someone!"
PRUNE_USAGE = (
    "💡 <b>Two-Way Wipe (/prune):</b>\n\n"
    "<i>Reply to any message (yours or your partner's) with</i> <code>/prune</code> "
    "<i>to permanently erase it for both of you!</i>"
)
PRUNE_UPGRADE_PROMPT = (
    "🔒 <b>Two-Way Wipe (/prune) is a VIP Feature!</b>\n\n"
    "<i>Permanently erase any message for both you and your partner with zero trace.\n"
    "Unlocked instantly on all VIP plans (starting at 25 ⭐ / ₹20).</i>"
)


async def prune_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Two-Way Message Eraser (/prune).
    Deletes the replied message on both the sender's and the partner's chat.
    Available for all VIP subscribers.
    """
    if not update.effective_user or not update.message:
        return

    if is_group_chat(update):
        return

    user_id = update.effective_user.id

    # 1. Must be in an active 1-on-1 chat
    if user_id not in init.active_pairs:
        await safe_tele_func_call(
            update.message.reply_text,
            text=PRUNE_NOT_IN_CHAT,
            parse_mode="HTML",
        )
        return

    partner_id = init.active_pairs[user_id]

    # 2. Must be replied to a message
    replied = update.message.reply_to_message
    if not replied:
        await safe_tele_func_call(
            update.message.reply_text,
            text=PRUNE_USAGE,
            parse_mode="HTML",
        )
        return

    # 3. Must be a subscribed VIP member
    if not is_subscribed(user_id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⚡ Unlock VIP (25 ⭐ / ₹20)", callback_data="sub|daily")],
            [InlineKeyboardButton("👑 View All VIP Plans", callback_data="sub|upgrade_prompt")],
        ])
        await safe_tele_func_call(
            update.message.reply_text,
            text=PRUNE_UPGRADE_PROMPT,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        return

    target_local_id = replied.message_id
    cmd_msg_id = update.message.message_id

    # 4. Check if the message is in the bidirectional message map
    mapped = init.message_map.get(user_id, {}).get(target_local_id)
    partner_target_id = None
    if mapped and mapped[0] == partner_id:
        partner_target_id = mapped[1]

    # 5. Delete on user's side
    await safe_tele_func_call(
        context.bot.delete_message,
        chat_id=user_id,
        message_id=target_local_id,
    )
    # Delete the /prune command message itself
    await safe_tele_func_call(
        context.bot.delete_message,
        chat_id=user_id,
        message_id=cmd_msg_id,
    )

    # 6. Delete on partner's side if mapped
    if partner_target_id:
        await safe_tele_func_call(
            context.bot.delete_message,
            chat_id=partner_id,
            message_id=partner_target_id,
        )

    # Clean up message_map
    if user_id in init.message_map:
        init.message_map[user_id].pop(target_local_id, None)
    if partner_id in init.message_map and partner_target_id:
        init.message_map[partner_id].pop(partner_target_id, None)
