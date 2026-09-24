import time
from typing import Dict
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from session_manager import is_in_chat, get_partner
from security import safe_tele_func_call
from message import NOT_IN_CHAT_TEXT

import init

NUDGE_COOLDOWN_SECONDS = 15
_nudge_timestamps: Dict[int, float] = {}


async def handle_nudge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Sends a subtle presence ping / nudge to the partner.
    Can be triggered via /nudge command or by tapping the '👋 Nudge' button below the typing area.
    """
    user_id = update.effective_user.id

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
        text="👋 <b>*NUDGE!*</b> Your partner is nudging you! Say hi 👋",
        parse_mode="HTML"
    )

    # Confirm to sender
    await safe_tele_func_call(
        update.message.reply_text,
        text="👋 <i>Nudge sent to your partner!</i>",
        parse_mode="HTML"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Checks the connection and last active status of the current partner.
    """
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
