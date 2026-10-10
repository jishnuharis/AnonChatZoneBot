from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from session_manager import end_chat_session, is_in_chat, get_partner
from saveNload import add_user_block, can_user_block
from message import NOT_IN_CHAT_TEXT

import init


@check_user_profile
async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Prompts the user with a confirmation dialog before blocking.
    Enforces active block limits (3 for free tier, 32 for subscribers).
    """
    from group_helper import is_group_chat, resolve_target, get_group_redirect_keyboard
    user_id = update.effective_user.id

    if is_group_chat(update):
        # 1. Resolve target
        target_res = await resolve_target(update, context)
        if not target_res:
            await safe_tele_func_call(
                update.message.reply_text,
                text="ℹ️ <i>Reply to a user's message with</i> <code>/block</code> <i>or type</i> <code>/block @username</code> <i>to block them!</i>",
                parse_mode="HTML"
            )
            return

        target_id, target_name = target_res

        # 2. Presence check: Prioritize sender first
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

        # 3. Target presence check
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
                text="😅 <i>You cannot block yourself!</i>",
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

        # 4. Check block limit & execute block
        allowed, count, limit = await can_user_block(user_id, target_id)
        if not allowed:
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>Block limit reached ({count}/{limit}).</b>\nPlease wait for an existing block to expire or upgrade with /subscribe.",
                parse_mode="HTML"
            )
            return

        await add_user_block(user_id, target_id)
        await safe_tele_func_call(
            update.message.reply_text,
            text=f"🚫 <b>User blocked!</b>\nYou will no longer be paired with <b>{target_name}</b> inside the bot for the next 24 hours.",
            parse_mode="HTML"
        )
        return

    if is_in_chat(user_id):
        partner_id = get_partner(user_id)
        if partner_id:
            allowed, count, limit = await can_user_block(user_id, partner_id)
            if not allowed:
                if limit == 3:
                    text = (
                        "⚠️ <b>Block limit reached (3/3).</b>\n\n"
                        "Free accounts can maintain up to 3 active 24-hour blocks at a time.\n"
                        "Upgrade with /subscribe for up to <b>32 blocks</b>, or wait for an earlier block to expire."
                    )
                else:
                    text = (
                        "⚠️ <b>Block limit reached (32/32).</b>\n\n"
                        "You have reached the maximum limit of 32 active blocks. Please wait for an existing block to expire."
                    )
                await safe_tele_func_call(update.message.reply_text, text=text, parse_mode="HTML")
                return

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🚫 Yes, Block Partner", callback_data=f"block_confirm|{partner_id}|active"),
                    InlineKeyboardButton("❌ Cancel", callback_data="block_cancel"),
                ]
            ])
            await safe_tele_func_call(
                update.message.reply_text,
                text=(
                    f"⚠️ <b>Are you sure you want to block your current partner?</b>\n\n"
                    f"• This chat will immediately end.\n"
                    f"• Neither of you will match with each other for the next 24 hours.\n"
                    f"• Active blocks used: <b>{count}/{limit}</b>"
                ),
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return

    # Check if there is a recent partner to block
    recent = init.recent_partners.get(user_id, [])
    if recent:
        target_id = recent[-1]
        allowed, count, limit = await can_user_block(user_id, target_id)
        if not allowed:
            if limit == 3:
                text = (
                    "⚠️ <b>Block limit reached (3/3).</b>\n\n"
                    "Free accounts can maintain up to 3 active 24-hour blocks at a time.\n"
                    "Upgrade with /subscribe for up to <b>32 blocks</b>, or wait for an earlier block to expire."
                )
            else:
                text = (
                    "⚠️ <b>Block limit reached (32/32).</b>\n\n"
                    "You have reached the maximum limit of 32 active blocks. Please wait for an existing block to expire."
                )
            await safe_tele_func_call(update.message.reply_text, text=text, parse_mode="HTML")
            return

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Yes, Block User", callback_data=f"block_confirm|{target_id}|recent"),
                InlineKeyboardButton("❌ Cancel", callback_data="block_cancel"),
            ]
        ])
        await safe_tele_func_call(
            update.message.reply_text,
            text=(
                f"⚠️ <b>Are you sure you want to block your previous partner?</b>\n\n"
                f"• Neither of you will match with each other for the next 24 hours.\n"
                f"• Active blocks used: <b>{count}/{limit}</b>"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        return

    await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")


async def handle_block_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles confirmation or cancellation of blocking."""
    query = update.callback_query
    await query.answer()
    data = query.data.split("|")
    action = data[0]
    user_id = update.effective_user.id

    if action == "block_cancel":
        await safe_tele_func_call(
            query.edit_message_text,
            text="❌ <i>Block cancelled. Chat remains unaffected.</i>",
            parse_mode="HTML"
        )
        return

    if action == "block_confirm":
        if len(data) < 3:
            return
        target_id = int(data[1])
        mode = data[2]

        allowed, count, limit = await can_user_block(user_id, target_id)
        if not allowed:
            if limit == 3:
                text = (
                    "⚠️ <b>Block limit reached (3/3).</b>\n\n"
                    "Free accounts can maintain up to 3 active 24-hour blocks at a time.\n"
                    "Upgrade with /subscribe for up to <b>32 blocks</b>, or wait for an earlier block to expire."
                )
            else:
                text = (
                    "⚠️ <b>Block limit reached (32/32).</b>\n\n"
                    "You have reached the maximum limit of 32 active blocks. Please wait for an existing block to expire."
                )
            await safe_tele_func_call(query.edit_message_text, text=text, parse_mode="HTML")
            return

        await add_user_block(user_id, target_id)

        if mode == "active":
            # If still connected with this partner, sever the chat
            current_partner = get_partner(user_id)
            if current_partner == target_id:
                await end_chat_session(
                    context,
                    user_id,
                    reason="blocked",
                    notify_initiator=False,
                    notify_partner=True,
                )
            await safe_tele_func_call(
                query.edit_message_text,
                text="🚫 <b>Partner blocked.</b> Chat ended. You will not be matched with them for the next 24 hours.",
                parse_mode="HTML"
            )
        else:
            await safe_tele_func_call(
                query.edit_message_text,
                text="🚫 <b>User blocked.</b> You will not be paired with them for the next 24 hours.",
                parse_mode="HTML"
            )
