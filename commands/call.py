import os
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import ContextTypes

import init
from handlers.setup import check_user_profile
from security import safe_tele_func_call
from session_manager import is_in_chat, get_partner
from message import (
    CALL_NOT_IN_CHAT_TEXT,
    CALL_ALREADY_ACTIVE_TEXT,
    CALL_LIMIT_REACHED_TEXT,
    CALL_INCOMING_TEXT,
    CALL_CALLING_PARTNER_TEXT,
    CALL_INVITATION_EXPIRED_TEXT,
    CALL_DECLINED_TEXT,
    CALL_PARTNER_DECLINED_TEXT,
    CALL_SESSION_ENDED_TEXT,
    CALL_CONNECTED_RECV_TEXT,
    CALL_CONNECTED_INIT_TEXT,
    CALL_ENDED_TEXT,
    CALL_PARTNER_ENDED_TEXT,
)

VOICE_CALL_BASE_URL = os.getenv("VOICE_CALL_WEBAPP_URL", "https://call.anonchatzone.org")

# session_id -> { "initiator": int, "receiver": int, "started_at": float, "status": str }
active_voice_calls = {}


@check_user_profile
async def call_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initiates an anonymous voice call request to the partner or target in group."""
    from group_helper import is_group_chat, resolve_target, get_group_redirect_keyboard
    user_id = update.effective_user.id

    if is_group_chat(update):
        # 1. Resolve target
        target_res = await resolve_target(update, context)
        if not target_res:
            await safe_tele_func_call(
                update.message.reply_text,
                text="ℹ️ <i>Reply to a user's message with</i> <code>/call</code> <i>or type</i> <code>/call @username</code> <i>to invite them to an anonymous voice call!</i>",
                parse_mode="HTML"
            )
            return

        target_id, target_name = target_res

        # 2. Check caller presence first
        if user_id not in init.user_details:
            await init.ensure_user_loaded(user_id)
        caller_data = init.user_details.get(user_id)
        if not caller_data or not all([caller_data.get("gender"), caller_data.get("age"), caller_data.get("country")]):
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
                text="😅 <i>You cannot call yourself!</i>",
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

        # 4. Check caller call limit
        from subscription import can_make_call
        allowed, used, limit = can_make_call(user_id)
        if not allowed:
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>Daily Voice Call Limit Reached ({used}/{limit}).</b>\nUpgrade to VIP with /subscribe for unlimited voice calls!",
                parse_mode="HTML"
            )
            return

        group_title = update.effective_chat.title or "our community group"
        caller_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        session_id = f"grpcall_{user_id}_{target_id}_{int(time.time())}"

        active_voice_calls[session_id] = {
            "initiator": user_id,
            "receiver": target_id,
            "created_at": time.time(),
            "status": "pending",
        }

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📞 Accept Call", callback_data=f"call_acc|{session_id}"),
                InlineKeyboardButton("❌ Decline", callback_data=f"call_dec|{session_id}"),
            ]
        ])

        dm_sent = await safe_tele_func_call(
            context.bot.send_message,
            chat_id=target_id,
            text=(
                f"📞 <b>Incoming Anonymous Voice Call Request!</b>\n\n"
                f"• <b>Caller:</b> {caller_tag}\n"
                f"• <b>From Group:</b> {group_title}\n\n"
                f"<i>Do you want to accept and join the anonymous voice room?</i>"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        if dm_sent:
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"📞 <b>{caller_tag} sent an anonymous voice call request to {target_name} in their DMs!</b>",
                parse_mode="HTML"
            )
        else:
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text=f"⚠️ <b>Could not reach {target_name} in private DM.</b>\nThey must start the bot first before receiving call requests.",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
        return

    if not is_in_chat(user_id):
        await safe_tele_func_call(
            update.message.reply_text,
            text=CALL_NOT_IN_CHAT_TEXT,
            parse_mode="HTML",
        )
        return

    partner_id = get_partner(user_id)
    if not partner_id:
        return

    session_id = init.active_sessions.get(user_id, f"{user_id}_{partner_id}")

    if session_id in active_voice_calls and active_voice_calls[session_id].get("status") == "active":
        await safe_tele_func_call(
            update.message.reply_text,
            text=CALL_ALREADY_ACTIVE_TEXT,
            parse_mode="HTML",
        )
        return

    from subscription import can_make_call, is_subscribed
    allowed, used, limit = can_make_call(user_id)
    if not allowed:
        await safe_tele_func_call(
            update.message.reply_text,
            text=CALL_LIMIT_REACHED_TEXT.format(used=used, limit=limit),
            parse_mode="HTML",
        )
        return

    active_voice_calls[session_id] = {
        "initiator": user_id,
        "receiver": partner_id,
        "created_at": time.time(),
        "status": "pending",
    }

    try:
        from streaks import record_chat_interaction
        record_chat_interaction(user_id, bot=getattr(context, "bot", None))
    except Exception as e:
        pass

    call_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📞 Accept Call", callback_data=f"call_acc|{session_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"call_dec|{session_id}"),
        ]
    ])

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=partner_id,
        text=CALL_INCOMING_TEXT,
        parse_mode="HTML",
        reply_markup=call_keyboard,
    )

    call_msg = CALL_CALLING_PARTNER_TEXT
    if not is_subscribed(user_id):
        remaining = max(0, limit - used)
        call_msg += f"\n\n<i>Daily free calls remaining today: {remaining}/{limit}</i>"

    await safe_tele_func_call(
        update.message.reply_text,
        text=call_msg,
        parse_mode="HTML",
    )


async def handle_call_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Accept or Decline on voice call requests."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    parts = (query.data or "").split("|")
    action = parts[0]
    session_id = parts[1] if len(parts) > 1 else ""

    call_data = active_voice_calls.get(session_id)
    if not call_data:
        await safe_tele_func_call(query.edit_message_text, text=CALL_INVITATION_EXPIRED_TEXT, parse_mode="HTML")
        return

    initiator = call_data["initiator"]
    receiver = call_data["receiver"]

    if user_id != receiver and user_id != initiator:
        return

    if action == "call_dec":
        active_voice_calls.pop(session_id, None)
        await safe_tele_func_call(query.edit_message_text, text=CALL_DECLINED_TEXT, parse_mode="HTML")
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=initiator,
            text=CALL_PARTNER_DECLINED_TEXT,
            parse_mode="HTML",
        )
        return

    if action == "call_acc":
        is_grp = session_id.startswith("grpcall_")
        if not is_grp and (not is_in_chat(user_id) or not is_in_chat(initiator)):
            active_voice_calls.pop(session_id, None)
            await safe_tele_func_call(query.edit_message_text, text=CALL_SESSION_ENDED_TEXT, parse_mode="HTML")
            return

        from subscription import consume_daily_call
        consume_daily_call(initiator)

        call_data["status"] = "active"

        try:
            from streaks import record_chat_interaction
            record_chat_interaction(user_id, bot=getattr(context, "bot", None))
        except Exception as e:
            pass

        # Construct anonymous WebApp URLs with ephemeral room token
        init_call_url = f"{VOICE_CALL_BASE_URL}/room/{session_id}?peer=1"
        recv_call_url = f"{VOICE_CALL_BASE_URL}/room/{session_id}?peer=2"

        init_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎙️ Join Voice Call", web_app=WebAppInfo(url=init_call_url))],
            [InlineKeyboardButton("🛑 End Call", callback_data=f"call_end|{session_id}")],
        ])
        recv_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎙️ Join Voice Call", web_app=WebAppInfo(url=recv_call_url))],
            [InlineKeyboardButton("🛑 End Call", callback_data=f"call_end|{session_id}")],
        ])

        await safe_tele_func_call(
            query.edit_message_text,
            text=CALL_CONNECTED_RECV_TEXT,
            parse_mode="HTML",
            reply_markup=recv_markup,
        )

        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=initiator,
            text=CALL_CONNECTED_INIT_TEXT,
            parse_mode="HTML",
            reply_markup=init_markup,
        )
        return

    if action == "call_end":
        active_voice_calls.pop(session_id, None)
        await safe_tele_func_call(query.edit_message_text, text=CALL_ENDED_TEXT, parse_mode="HTML")
        other_user = initiator if user_id == receiver else receiver
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=other_user,
            text=CALL_PARTNER_ENDED_TEXT,
            parse_mode="HTML",
        )
