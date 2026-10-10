import time
from typing import Dict
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from session_manager import is_in_chat, get_partner
from security import safe_tele_func_call
from message import NOT_IN_CHAT_TEXT

from group_helper import is_group_chat, reply_group_redirect, resolve_target, get_group_redirect_keyboard
import init

NUDGE_COOLDOWN_SECONDS = 15
_nudge_timestamps: Dict[int, float] = {}


async def handle_nudge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a subtle presence ping / nudge to the partner in DM,
    or tags and nudges a target user inside a group.
    """
    user_id = update.effective_user.id

    if is_group_chat(update):
        # 1. Target resolution
        target_res = await resolve_target(update, context)
        if not target_res:
            await safe_tele_func_call(
                update.message.reply_text,
                text="ℹ️ <i>Reply to a user's message with</i> <code>/nudge</code> <i>or type</i> <code>/nudge @username</code> <i>to nudge them!</i>",
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
                text="😅 <i>You cannot nudge yourself!</i>",
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

        # 4. Cooldown
        now = time.time()
        last_nudge = _nudge_timestamps.get(user_id, 0)
        remaining = int(NUDGE_COOLDOWN_SECONDS - (now - last_nudge))
        if remaining > 0:
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⏳ <i>Please wait {remaining}s before nudging again.</i>",
                parse_mode="HTML"
            )
            return

        _nudge_timestamps[user_id] = now
        init.last_activity[user_id] = now

        sender_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        await safe_tele_func_call(
            update.message.reply_text,
            text=f"👋 Hey <b>{target_name}</b>, <b>{sender_tag}</b> nudged you! Wake up! 🔔",
            parse_mode="HTML"
        )
        return

    if not is_in_chat(user_id):
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return

    partner_id = get_partner(user_id)
    if not partner_id:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return

    now = time.time()
    last_nudge = _nudge_timestamps.get(user_id, 0)
    remaining = int(NUDGE_COOLDOWN_SECONDS - (now - last_nudge))
    if remaining > 0:
        await safe_tele_func_call(
            update.message.reply_text,
            text=f"⏳ <i>Please wait {remaining}s before nudging again.</i>",
            parse_mode="HTML"
        )
        return

    _nudge_timestamps[user_id] = now
    init.last_activity[user_id] = now

    # Dispatch typing chat action to partner
    await safe_tele_func_call(context.bot.send_chat_action, chat_id=partner_id, action=ChatAction.TYPING)

    # Deliver nudge to partner
    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=partner_id,
        text="👋 <b>NUDGE!</b>\nYour partner is nudging you! Say hi 👋",
        parse_mode="HTML"
    )

    # Confirm to sender
    await safe_tele_func_call(
        update.message.reply_text,
        text="👋 <i>Nudge sent to your partner!</i>",
        parse_mode="HTML"
    )

    try:
        from streaks import record_chat_interaction
        record_chat_interaction(user_id, bot=getattr(context, "bot", None))
    except Exception as e:
        pass


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Checks the connection and last active status of the current partner.
    """
    if is_group_chat(update):
        return await reply_group_redirect(update, context, start_arg="group")

    user_id = update.effective_user.id

    if not is_in_chat(user_id):
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return

    partner_id = get_partner(user_id)
    if not partner_id:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_TEXT, parse_mode="HTML")
        return

    init.last_activity[user_id] = time.time()
    last_active = init.last_activity.get(partner_id)

    if last_active:
        diff = int(time.time() - last_active)
        if diff < 10:
            time_str = "Active right now"
        elif diff < 60:
            time_str = f"{diff}s ago"
        elif diff < 3600:
            time_str = f"{diff // 60}m ago"
        else:
            time_str = f"{diff // 3600}h ago"
    else:
        time_str = "Active recently"

    await safe_tele_func_call(
        update.message.reply_text,
        text=(
            f"🟢 <b>Partner Status:</b> Connected\n"
            f"⏱️ <b>Last active:</b> {time_str}\n\n"
            f"<i>Remember: Silence ≠ disconnect. Your chat stays active indefinitely!</i>"
        ),
        parse_mode="HTML"
    )
