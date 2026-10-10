from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from games.registry import get_active, end_any_active_game
from message import (
    GAME_CANCELLED_TEXT, GAME_REQUEST_CANCELLED_TEXT, PARTNER_CANCELLED_REQUEST_TEXT,
    NOTHING_TO_CANCEL_TEXT,
)

import init


@check_user_profile
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    from group_helper import is_group_chat, is_group_admin
    if is_group_chat(update):
        if not await is_group_admin(context, update.effective_chat.id, user_id):
            await safe_tele_func_call(
                update.message.reply_text,
                text="⛔ <b>Only group admins can cancel active games or challenges in this group.</b>",
                parse_mode="HTML"
            )
            return

        chat_id = update.effective_chat.id
        cancelled_any = False
        for gid, gdata in list(init.group_games.items()):
            if gdata.get("chat_id") == chat_id or gdata.get("group_id") == chat_id:
                init.group_games.pop(gid, None)
                p1 = gdata.get("challenger_id")
                p2 = gdata.get("opponent_id")
                if p1:
                    await end_any_active_game(context, p1)
                if p2:
                    await end_any_active_game(context, p2)
                cancelled_any = True

        if cancelled_any:
            await safe_tele_func_call(
                update.message.reply_text,
                text="🛑 <b>The active group game or challenge was cancelled by an admin.</b>",
                parse_mode="HTML"
            )
        else:
            await safe_tele_func_call(
                update.message.reply_text,
                text="ℹ️ <b>There is no active game or challenge to cancel in this group.</b>",
                parse_mode="HTML"
            )
        return

    if get_active(user_id):
        await end_any_active_game(context, user_id)
        await safe_tele_func_call(update.message.reply_text, text=GAME_CANCELLED_TEXT, parse_mode="HTML")
        return

    incoming = init.game_requests.get(user_id)
    if incoming:
        requester_id = incoming["from"]
        init.game_requests.pop(user_id, None)
        await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
        return

    for target_id, req in list(init.game_requests.items()):
        if req["from"] == user_id:
            init.game_requests.pop(target_id, None)
            await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=PARTNER_CANCELLED_REQUEST_TEXT, parse_mode="HTML")
            await safe_tele_func_call(update.message.reply_text, text=GAME_REQUEST_CANCELLED_TEXT, parse_mode="HTML")
            return

    if user_id in init.waiting_users:
        from matchmaking import dequeue_user
        from message import REMOVED_FROM_QUEUE_TEXT
        from session_manager import IDLE_KEYBOARD
        await dequeue_user(user_id)
        await safe_tele_func_call(update.message.reply_text, text=REMOVED_FROM_QUEUE_TEXT, reply_markup=IDLE_KEYBOARD, parse_mode="HTML")
        return

    await safe_tele_func_call(update.message.reply_text, text=NOTHING_TO_CANCEL_TEXT, parse_mode="HTML")
