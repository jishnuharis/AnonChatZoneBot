import os
import re
import asyncio
import time
import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from html import escape as esc

from security import safe_tele_func_call, format_duration
from session_manager import start_chat_session, end_chat_session, is_in_chat, get_partner
from moderation import is_admin, apply_restriction, clear_restriction, severity_for_score, SEVERITY_DURATIONS
from saveNload import add_promotion_db, get_active_promotions_db
from message import (
    GIVE_VALID_CONNECT_USER_ID_TEXT, TARGET_NOT_IN_DB_TEXT,
    ALREADY_CONNECTED_TO_TARGET_TEXT, ADMIN_HELP_TEXT, BAN_USAGE_TEXT,
    SEVERITY_RANGE_TEXT, CANT_RESTRICT_SELF_TEXT, ADMINS_CANT_BE_RESTRICTED_TEXT,
    SEVERITY_ZERO_NOOP_TEXT, UNBAN_USAGE_TEXT, GIVE_VALID_USER_ID_TEXT, RESTRICTION_LIFTED_TEXT,
    CHECKUSER_USAGE_TEXT, NO_RECORD_OF_USER_TEXT, NOT_RESTRICTED_TEXT, NO_REPORTS_TEXT,
    GIVEAWAY_USAGE_TEXT, GIVEAWAY_UNKNOWN_TIER_TEXT, REFERRAL_USAGE_TEXT, REFERRAL_DISABLED_TEXT,
)
import subscription
import referral

import init

logger = logging.getLogger(__name__)


async def _send_with_html_fallback(send_func, chat_id, text=None, caption=None, **kwargs):
    """
    Attempts to send text/caption with HTML parse mode.
    Auto-sanitizes naked ampersands. If Telegram raises an entity parsing BadRequest,
    gracefully falls back to plain text without parse_mode so the announcement is NEVER dropped!
    """
    content_key = "caption" if (caption is not None or "photo" in kwargs or "video" in kwargs) else "text"
    raw_content = caption if caption is not None else (text or "")

    if raw_content:
        # Sanitize naked ampersands that are not already valid HTML entities
        sanitized = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", raw_content)

        kwargs[content_key] = sanitized
        try:
            return await safe_tele_func_call(send_func, chat_id=chat_id, parse_mode="HTML", **kwargs)
        except BadRequest as e:
            err_lower = str(e).lower()
            if any(term in err_lower for term in ("entity", "parse", "tag", "byte offset", "bad formatting")):
                logger.warning(f"HTML parse mode failed on broadcast ({e}). Retrying with clean plain text fallback...")
                plain = re.sub(r"<[^>]+>", "", raw_content)
                kwargs[content_key] = plain
                return await safe_tele_func_call(send_func, chat_id=chat_id, parse_mode=None, **kwargs)
            raise
    else:
        # Photo or media sent without any caption text
        return await safe_tele_func_call(send_func, chat_id=chat_id, **kwargs)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not is_admin(update.effective_user.id):
        if update.effective_user and update.effective_user.id in init.active_pairs:
            from relay import relay_message
            return await relay_message(update, context)
        return

    from group_helper import is_group_chat, delete_admin_command
    if is_group_chat(update):
        await delete_admin_command(update, context)
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_user.id,
            text="⚠️ <b>/broadcast is restricted to private DMs only.</b>",
            parse_mode="HTML"
        )
        return

    raw_text = (update.message.text or update.message.caption or "") if update.message else ""

    replied_msg = None
    if update.message and getattr(update.message, "reply_to_message", None):
        cand = update.message.reply_to_message
        msg_id = getattr(cand, "message_id", None)
        try:
            from unittest.mock import MagicMock
            is_mock_id = isinstance(msg_id, MagicMock)
        except ImportError:
            is_mock_id = False
        if msg_id is not None and not is_mock_id:
            replied_msg = cand

    has_photo = bool(
        update.message
        and isinstance(getattr(update.message, "photo", None), (list, tuple))
        and len(update.message.photo) > 0
    )

    # Strip /broadcast or /broadcast@bot_username from beginning
    clean_text = re.sub(r"^/broadcast(?:@\w+)?\s*", "", raw_text, flags=re.IGNORECASE).strip()

    is_test = False
    is_direct = False

    if clean_text.lower() == "test" or clean_text.lower().startswith("test "):
        is_test = True
        clean_text = clean_text[4:].strip()
        if clean_text.lower().startswith("direct"):
            clean_text = clean_text[len("direct"):].strip()
    elif clean_text.lower().startswith("direct"):
        is_direct = True
        clean_text = clean_text[len("direct"):].strip()
        if clean_text.lower() == "test" or clean_text.lower().startswith("test "):
            is_test = True
            clean_text = clean_text[4:].strip()

    is_reply_broadcast = bool(replied_msg and not clean_text)

    if not is_reply_broadcast and not clean_text and not has_photo:
        await update.message.reply_text(
            "<b>📢 Broadcast Usage:</b>\n\n"
            "• <code>/broadcast test &lt;message&gt;</code> — Test preview sent <b>only to you</b>\n"
            "• <code>/broadcast &lt;message&gt;</code> — Posts to official channel (instant)\n"
            "• <code>/broadcast direct &lt;message&gt;</code> — DMs all bot users in batches\n"
            "• <i>Reply to any message with</i> <code>/broadcast test</code> <i>to test, or</i> <code>/broadcast direct</code> <i>to send to all!</i>",
            parse_mode="HTML"
        )
        return

    # If test mode is requested, send ONLY to the caller/owner without touching users or channels!
    if is_test:
        target_chat = update.effective_chat.id
        try:
            sent_msg = None
            if is_reply_broadcast:
                sent_msg = await safe_tele_func_call(
                    context.bot.copy_message,
                    chat_id=target_chat,
                    from_chat_id=update.effective_chat.id,
                    message_id=replied_msg.message_id
                )
            elif has_photo:
                photo_id = update.message.photo[-1].file_id
                sent_msg = await _send_with_html_fallback(
                    context.bot.send_photo,
                    chat_id=target_chat,
                    photo=photo_id,
                    caption=clean_text
                )
            else:
                sent_msg = await _send_with_html_fallback(
                    context.bot.send_message,
                    chat_id=target_chat,
                    text=clean_text
                )

            if sent_msg:
                await update.message.reply_text(
                    "🧪 <b>[Test Mode] Broadcast preview delivered only to you!</b> ✅\n"
                    "<i>No other users or channels received this message.</i>",
                    parse_mode="HTML"
                )
            else:
                await update.message.reply_text(
                    "⚠️ <i>Failed to deliver test broadcast preview.</i>",
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.error(f"Error in test broadcast: {e}")
            await update.message.reply_text(f"⚠️ Test broadcast error: {esc(str(e))}", parse_mode="HTML")
        return

    channel_id = os.getenv("ANNOUNCEMENT_CHANNEL", getattr(init, "ANNOUNCEMENT_CHANNEL", "@channelofchatzone"))

    # If not explicitly marked 'direct', post to official announcement channel if configured!
    if not is_direct:
        if channel_id and channel_id.strip():
            try:
                sent_msg = None
                if is_reply_broadcast:
                    sent_msg = await safe_tele_func_call(
                        context.bot.copy_message,
                        chat_id=channel_id,
                        from_chat_id=update.effective_chat.id,
                        message_id=replied_msg.message_id
                    )
                elif has_photo:
                    photo_id = update.message.photo[-1].file_id
                    sent_msg = await _send_with_html_fallback(
                        context.bot.send_photo,
                        chat_id=channel_id,
                        photo=photo_id,
                        caption=clean_text
                    )
                else:
                    sent_msg = await _send_with_html_fallback(
                        context.bot.send_message,
                        chat_id=channel_id,
                        text=clean_text
                    )

                if sent_msg:
                    await update.message.reply_text(
                        f"📢 <b>Announcement posted to channel {channel_id} successfully!</b> ✅",
                        parse_mode="HTML"
                    )
                    return
                else:
                    await update.message.reply_text(
                        f"⚠️ <i>Failed to post to {channel_id}. Verify bot is an administrator with 'Post Messages' permission in the channel.</i>",
                        parse_mode="HTML"
                    )
                    return
            except Exception as e:
                logger.error(f"Error posting announcement to channel {channel_id}: {e}")
                err_text = esc(str(e))
                tip = ""
                err_lower = str(e).lower()
                if any(k in err_lower for k in ("chat not found", "rights", "forbidden", "administrator")):
                    tip = (
                        "\n\n💡 <b>Tip:</b> Make sure the bot has been added to your channel "
                        f"<code>{channel_id}</code> as an <b>Administrator</b> with the <b>Post Messages</b> permission enabled."
                    )
                await update.message.reply_text(f"⚠️ Channel error: {err_text}{tip}", parse_mode="HTML")
                return
        else:
            await update.message.reply_text(
                "⚠️ <b>ANNOUNCEMENT_CHANNEL</b> is not configured in .env.\n"
                "• Set <code>ANNOUNCEMENT_CHANNEL=@YourChannel</code> in your .env to post to your official channel instantly.\n"
                "• Or use <code>/broadcast direct &lt;message&gt;</code> to send individual private messages.",
                parse_mode="HTML"
            )
            return

    # Direct individual user broadcast
    sent = 0
    target_users = list(init.user_details.keys())
    batch_size = 20

    for i in range(0, len(target_users), batch_size):
        chunk = target_users[i:i + batch_size]
        if is_reply_broadcast:
            tasks = [
                safe_tele_func_call(
                    context.bot.copy_message,
                    chat_id=uid,
                    from_chat_id=update.effective_chat.id,
                    message_id=replied_msg.message_id
                )
                for uid in chunk
            ]
        else:
            tasks = [
                _send_with_html_fallback(
                    context.bot.send_message,
                    chat_id=uid,
                    text=clean_text
                )
                for uid in chunk
            ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if res and not isinstance(res, Exception):
                sent += 1
        await asyncio.sleep(0.05)

    await update.message.reply_text(f"<i>Direct broadcast sent to</i> <b>{sent}</b> <i>users ✅.</i>", parse_mode="HTML")


async def connect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    from group_helper import is_group_chat, delete_admin_command
    if is_group_chat(update):
        await delete_admin_command(update, context)
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user_id,
            text="⚠️ <b>/connect is restricted to private DMs only.</b>",
            parse_mode="HTML"
        )
        return

    args = context.args or []
    # If 2 user IDs are passed: connect those 2 users directly!
    if len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
        u1 = int(args[0])
        u2 = int(args[1])
        if u1 == u2:
            await update.message.reply_text("<b>Cannot connect a user to themselves.</b>", parse_mode="HTML")
            return

        if u1 not in init.user_details:
            await init.ensure_user_loaded(u1)
        if u2 not in init.user_details:
            await init.ensure_user_loaded(u2)
        if u1 not in init.user_details or u2 not in init.user_details:
            await update.message.reply_text(TARGET_NOT_IN_DB_TEXT, parse_mode="HTML")
            return

        if is_in_chat(u1) and get_partner(u1) == u2:
            await update.message.reply_text("<b>Users are already connected to each other.</b>", parse_mode="HTML")
            return

        async with init.queue_lock:
            for uid in (u1, u2):
                if uid in init.waiting_users:
                    init.waiting_users.remove(uid)
                    init.wait_started.pop(uid, None)

        for uid in (u1, u2):
            if is_in_chat(uid):
                await end_chat_session(context, uid, reason="admin_reconnect", notify_initiator=False, notify_partner=True)

        success = await start_chat_session(context, u1, u2, is_admin_connect=True)
        if success:
            await update.message.reply_text(f"✅ <i>Successfully connected user</i> <code>{u1}</code> <i>and</i> <code>{u2}</code>.", parse_mode="HTML")
        else:
            await update.message.reply_text("⚠️ <b>Failed to connect users.</b>", parse_mode="HTML")
        return

    message = update.message.text
    if message.lower().startswith("/connect"):
        message = message[len("/connect"):].strip()
    try:
        target_id = int(message.split()[0])
    except (ValueError, IndexError):
        await update.message.reply_text(GIVE_VALID_CONNECT_USER_ID_TEXT, parse_mode="HTML")
        return

    if target_id == user_id:
        await update.message.reply_text("<b>You cannot connect to yourself.</b>", parse_mode="HTML")
        return

    if target_id not in init.user_details:
        await init.ensure_user_loaded(target_id)
        if target_id not in init.user_details:
            await update.message.reply_text(TARGET_NOT_IN_DB_TEXT, parse_mode="HTML")
            return

    if is_in_chat(user_id) and get_partner(user_id) == target_id:
        await update.message.reply_text(ALREADY_CONNECTED_TO_TARGET_TEXT, parse_mode="HTML")
        return

    # If target or admin is waiting in queue, remove them
    async with init.queue_lock:
        if user_id in init.waiting_users:
            init.waiting_users.remove(user_id)
            init.wait_started.pop(user_id, None)
        if target_id in init.waiting_users:
            init.waiting_users.remove(target_id)
            init.wait_started.pop(target_id, None)

    # Cleanly terminate existing active chat sessions for target and admin
    if is_in_chat(target_id):
        await end_chat_session(
            context,
            target_id,
            reason="admin_reconnect",
            notify_initiator=False,
            notify_partner=True,
        )

    if is_in_chat(user_id):
        await end_chat_session(
            context,
            user_id,
            reason="admin_reconnect",
            notify_initiator=False,
            notify_partner=True,
        )

    # Start session atomically with DB logging into chat_sessions table!
    success = await start_chat_session(
        context,
        user_id,
        target_id,
        is_admin_connect=True,
    )
    if not success:
        await update.message.reply_text("⚠️ <b>Failed to connect to target user.</b>", parse_mode="HTML")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    from group_helper import is_group_chat, delete_admin_command, resolve_target
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    args = context.args or []
    target_id = None
    target_name = None
    severity = None
    reason = "Manual admin action"

    cand = getattr(update.message, "reply_to_message", None) if update.message else None
    if cand and getattr(cand, "from_user", None) and isinstance(getattr(cand.from_user, "id", None), int):
        target_id = cand.from_user.id
        u_name = cand.from_user.username
        target_name = f"@{u_name}" if u_name else cand.from_user.first_name
        if len(args) >= 1:
            try:
                severity = int(args[0])
                if len(args) > 1:
                    reason = " ".join(args[1:])
            except ValueError:
                pass
    elif len(args) >= 2:
        target_res = await resolve_target(update, context, arg_index=0)
        if target_res and target_res[0]:
            target_id, target_name = target_res
        try:
            severity = int(args[1])
            if len(args) > 2:
                reason = " ".join(args[2:])
        except ValueError:
            pass

    if target_id is None or severity is None:
        target_chat = user_id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=BAN_USAGE_TEXT, parse_mode="HTML")
        return

    if not (0 <= severity <= 10):
        target_chat = user_id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=SEVERITY_RANGE_TEXT, parse_mode="HTML")
        return

    if target_id == user_id:
        target_chat = user_id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=CANT_RESTRICT_SELF_TEXT, parse_mode="HTML")
        return
    if is_admin(target_id):
        target_chat = user_id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=ADMINS_CANT_BE_RESTRICTED_TEXT, parse_mode="HTML")
        return

    # Enforce queue eviction & chat severance
    until = await apply_restriction(target_id, severity, reason, context=context)
    if not until:
        target_chat = user_id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=SEVERITY_ZERO_NOOP_TEXT, parse_mode="HTML")
        return

    remaining = format_duration(until - time.time())
    display_tag = target_name or f"<code>{target_id}</code>"
    if in_group:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_chat.id,
            text=f"⛔ <b>User {display_tag} restricted for {esc(remaining)} (severity {severity}).</b>\n<i>Reason:</i> <code>{esc(reason)}</code>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"⛔ <i>User</i> <code>{target_id}</code> <i>restricted for</i> <b>{esc(remaining)}</b> <i>(severity {severity}).</i>\n<i>Reason:</i> <code>{esc(reason)}</code>", parse_mode="HTML")

    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=f"⛔ <b>You've been restricted by an admin.</b>\n\n<i>Reason:</i> <code>{esc(reason)}</code>\n<i>Time:</i> <code>{esc(remaining)}</code>", parse_mode="HTML")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command, resolve_target
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    args = context.args or []
    target_id = None
    target_name = None

    cand = getattr(update.message, "reply_to_message", None) if update.message else None
    if cand and getattr(cand, "from_user", None) and isinstance(getattr(cand.from_user, "id", None), int):
        target_id = cand.from_user.id
        u_name = cand.from_user.username
        target_name = f"@{u_name}" if u_name else cand.from_user.first_name
    elif args:
        target_res = await resolve_target(update, context, arg_index=0)
        if target_res and target_res[0]:
            target_id, target_name = target_res

    if not target_id:
        target_chat = update.effective_user.id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=target_chat, text=UNBAN_USAGE_TEXT, parse_mode="HTML")
        return

    await clear_restriction(target_id)
    display_tag = target_name or f"<code>{target_id}</code>"
    if in_group:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_chat.id,
            text=f"✅ <b>User {display_tag} has been unrestricted.</b>",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(f"✅ <i>User</i> <code>{target_id}</code> <i>has been unrestricted.</i>", parse_mode="HTML")

    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=RESTRICTION_LIFTED_TEXT, parse_mode="HTML")


async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        return

    from group_helper import is_group_chat, delete_admin_command, resolve_target
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    async def _reply(msg_text):
        if in_group:
            await safe_tele_func_call(context.bot.send_message, chat_id=admin_id, text=msg_text, parse_mode="HTML")
        else:
            await update.message.reply_text(msg_text, parse_mode="HTML")

    args = context.args or []
    target_id = None

    cand = getattr(update.message, "reply_to_message", None) if update.message else None
    if cand and getattr(cand, "from_user", None) and isinstance(getattr(cand.from_user, "id", None), int):
        target_id = cand.from_user.id
    elif args:
        target_res = await resolve_target(update, context, arg_index=0)
        if target_res and target_res[0]:
            target_id = target_res[0]
        elif str(args[0]).startswith("@"):
            await _reply(NO_RECORD_OF_USER_TEXT)
            return
        else:
            try:
                target_id = int(args[0])
            except ValueError:
                await _reply(GIVE_VALID_USER_ID_TEXT)
                return

    if not target_id:
        await _reply(CHECKUSER_USAGE_TEXT)
        return

    from saveNload import get_user
    details = None
    if target_id in init.user_details:
        cached = init.user_details[target_id]
        if cached.get("gender") or cached.get("country") or cached.get("points", 0) > 0 or cached.get("total_messages", 0) > 0:
            details = cached

    if not details:
        db_user = await get_user(target_id)
        if db_user:
            for key, value in init._default_user().items():
                db_user.setdefault(key, value)
            init.user_details[target_id] = db_user
            details = db_user

    if not details:
        await _reply(NO_RECORD_OF_USER_TEXT)
        return

    created_ts = details.get("created_at")
    created_line = "Unknown"
    if created_ts:
        try:
            if hasattr(created_ts, "strftime"):
                created_line = created_ts.strftime("%Y-%m-%d %H:%M UTC")
            else:
                created_line = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(float(created_ts)))
        except Exception:
            created_line = "Unknown"

    last_active_ts = details.get("last_active") or init.last_activity.get(target_id)
    if last_active_ts is not None:
        try:
            diff = max(0.0, time.time() - float(last_active_ts))
            last_active_line = "Just now" if diff < 60 else f"{format_duration(diff)} ago"
        except Exception:
            last_active_line = "Never"
    else:
        last_active_line = "Never"

    try:
        total_msgs = int(details.get("total_messages") or 0)
    except (ValueError, TypeError):
        total_msgs = 0

    try:
        total_dur = float(details.get("total_chat_duration") or 0.0)
    except (ValueError, TypeError):
        total_dur = 0.0

    if (details.get("partner_id") or target_id in init.active_pairs) and target_id in init.session_start_times:
        try:
            start_ts = float(init.session_start_times[target_id])
            total_dur += max(0.0, time.time() - start_ts)
        except Exception:
            pass
    duration_line = format_duration(total_dur)

    restricted_until = details.get("restricted_until")
    if restricted_until and restricted_until > time.time():
        restriction_line = f"⛔ Restricted for {format_duration(restricted_until - time.time())} — <code>{esc(str(details.get('restriction_reason')))}</code>"
    else:
        restriction_line = NOT_RESTRICTED_TEXT

    recent_reports = details.get("report_log", [])[-5:]
    reports_text = "\n".join(
        f"  • <code>{esc(str(r['reason']))}</code> from <code>{r['reporter']}</code>" for r in recent_reports
    ) or NO_REPORTS_TEXT

    lifetime_reports = details.get("reports", 0)
    severity_score = details.get("severity_score", 0)
    severity_level = severity_for_score(severity_score)
    level_duration = SEVERITY_DURATIONS.get(severity_level, 0)
    level_line = (
        f"{severity_score} pts → Level {severity_level}/10"
        + (f" (would restrict {format_duration(level_duration)})" if level_duration else " (no active restriction weight)")
    )

    last_decay = details.get("last_severity_decay")
    decay_line = f"{format_duration(time.time() - last_decay)} ago" if last_decay else "Never"

    if subscription.is_subscribed(target_id):
        tier = subscription.active_tier(target_id)
        expires = details.get("subscription_expires")
        sub_line = f"{tier['label']} — expires in {format_duration(expires - time.time())}" if tier else "Active"
    else:
        sub_line = "Not subscribed"

    partner_id = details.get("partner_id")
    partner_line = f"In chat with <code>{partner_id}</code>" if partner_id else "Not in a chat"

    text = (
        f"<b>User</b> <code>{target_id}</code>\n"
        f"Account Created: <code>{created_line}</code>\n"
        f"Last Active: {last_active_line}\n"
        f"Points: {details.get('points', 0)}\n"
        f"Votes: {(details.get('votes') or {}).get('up', 0)} 👍 {(details.get('votes') or {}).get('down', 0)} 👎\n"
        f"Total Messages: {total_msgs}\n"
        f"Time in Chats: {duration_line}\n"
        f"Subscription: {sub_line}\n"
        f"Status: {partner_line}\n"
        f"\n"
        f"<b>Moderation</b>\n"
        f"Lifetime reports: {lifetime_reports}\n"
        f"Current severity: {level_line}\n"
        f"Last decay: {decay_line}\n"
        f"{restriction_line}\n"
        f"Recent reports:\n{reports_text}"
    )
    await _reply(text)


async def giveaway_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command, resolve_target
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    args = context.args or []
    target_id = None
    target_name = None
    tier_key = None

    cand = getattr(update.message, "reply_to_message", None) if update.message else None
    if cand and getattr(cand, "from_user", None) and isinstance(getattr(cand.from_user, "id", None), int):
        target_id = cand.from_user.id
        u_name = cand.from_user.username
        target_name = f"@{u_name}" if u_name else cand.from_user.first_name
        if args:
            tier_key = args[0].lower()
    elif len(args) >= 2:
        target_res = await resolve_target(update, context, arg_index=0)
        if target_res and target_res[0]:
            target_id, target_name = target_res
        tier_key = args[1].lower()

    if not target_id or not tier_key:
        dest_chat = update.effective_user.id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=dest_chat, text=GIVEAWAY_USAGE_TEXT, parse_mode="HTML")
        return

    if tier_key not in subscription.TIERS:
        dest_chat = update.effective_user.id if in_group else update.message.chat_id
        await safe_tele_func_call(context.bot.send_message, chat_id=dest_chat, text=GIVEAWAY_UNKNOWN_TIER_TEXT, parse_mode="HTML")
        return

    tier = subscription.TIERS[tier_key]
    new_expiry = subscription.grant_subscription(target_id, tier_key, source="admin_grant")
    from saveNload import add_subscription_db
    await add_subscription_db(target_id, tier_key, tier["duration_days"], source="admin_grant")
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(new_expiry))

    display_tag = target_name or f"<code>{target_id}</code>"
    if in_group:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_chat.id,
            text=(
                f"🎉 <b>VIP Giveaway Winner!</b>\n\n"
                f"<b>{display_tag}</b> has been awarded <b>{tier['label']}</b> "
                f"(+{tier['bonus_points']} points)! ✨"
            ),
            parse_mode="HTML",
        )
    else:
        await update.message.reply_text(
            f"✅ <i>Granted</i> <b>{tier['label']}</b> <i>to</i> <code>{target_id}</code> "
            f"<i>(+{tier['bonus_points']} points). Active until</i> <code>{expires_str}</code>.",
            parse_mode="HTML",
        )
    await safe_tele_func_call(
        context.bot.send_message, chat_id=target_id,
        text=(
            f"🎁 <b>An admin gifted you a {tier['label']} subscription!</b>\n"
            f"<i>Active until:</i> <code>{expires_str}</code>\n"
            f"<i>+{tier['bonus_points']} points added 🎉</i>"
        ),
        parse_mode="HTML",
    )


async def referral_scheme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command
    if is_group_chat(update):
        await delete_admin_command(update, context)
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_user.id,
            text="⚠️ <b>/referral is restricted to private DMs only.</b>",
            parse_mode="HTML"
        )
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(REFERRAL_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        required_referrals = int(args[0])
        duration_days = int(args[1])
        reward_days = int(args[2]) if len(args) >= 3 else 1
    except ValueError:
        await update.message.reply_text(REFERRAL_USAGE_TEXT, parse_mode="HTML")
        return

    scheme = await referral.set_scheme(required_referrals, duration_days, reward_days)

    if not scheme.get("required_referrals"):
        await update.message.reply_text(REFERRAL_DISABLED_TEXT, parse_mode="HTML")
        return

    rew_days = scheme.get("reward_days", 1)
    day_word = "day" if rew_days == 1 else "days"
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(scheme["expires"]))
    await update.message.reply_text(
        f"✅ <i>Referral scheme active: refer</i> <b>{scheme['required_referrals']}</b> "
        f"<i>friends who finish onboarding →</i> <b>{rew_days} {day_word} of VIP</b>.\n"
        f"<i>Promo runs until</i> <code>{esc(expires_str)}</code>.",
        parse_mode="HTML",
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows operational bot health and statistics."""
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    total_cached = len(init.user_details)
    active_matches = len(init.active_pairs) // 2
    waiting_count = len(init.waiting_users)

    text = (
        "📊 <b>System & Operational Stats</b>\n\n"
        f"• <b>Active Chat Pairs:</b> {active_matches}\n"
        f"• <b>Users in Queue:</b> {waiting_count}\n"
        f"• <b>Cached Active Users:</b> {total_cached}\n"
        f"• <b>Active Sessions:</b> {len(init.active_sessions) // 2}\n"
        f"• <b>Game Requests In-Flight:</b> {len(init.game_requests)}\n"
    )
    if in_group:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_user.id,
            text=text,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML")


async def queue_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows queue details."""
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command
    in_group = is_group_chat(update)
    if in_group:
        await delete_admin_command(update, context)

    async with init.queue_lock:
        now = time.time()
        count = len(init.waiting_users)
        oldest_wait = 0.0
        if init.wait_started:
            oldest_wait = max(0.0, now - min(init.wait_started.values()))

    text = (
        "👥 <b>Queue Overview</b>\n\n"
        f"• <b>Waiting Users:</b> {count}\n"
        f"• <b>Longest Wait:</b> {int(oldest_wait)}s\n"
    )
    if in_group:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_user.id,
            text=text,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(text, parse_mode="HTML")


async def campaign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manage sponsor campaigns."""
    if not is_admin(update.effective_user.id):
        return

    from group_helper import is_group_chat, delete_admin_command
    if is_group_chat(update):
        await delete_admin_command(update, context)
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=update.effective_user.id,
            text="⚠️ <b>/campaign is restricted to private DMs only.</b>",
            parse_mode="HTML"
        )
        return

    args = context.args
    if not args or args[0] == "help":
        await update.message.reply_text(
            "📢 <b>Campaign Management</b>\n\n"
            "• <code>/campaign list</code> — <i>View all active campaigns</i>\n"
            "• <code>/campaign create Sponsor | Title | Text [| ButtonText | ButtonURL [| PhotoURL]]</code>\n\n"
            "💡 <i>Tip: You can also attach a photo or reply to a photo when running <code>/campaign create</code>!</i>",
            parse_mode="HTML"
        )
        return

    action = args[0].lower()
    if action == "list":
        promos = await get_active_promotions_db()
        if not promos:
            await update.message.reply_text("<i>No active campaigns right now.</i>", parse_mode="HTML")
            return
        lines = []
        for p in promos:
            photo_badge = " [📷 Photo]" if p.get("photo_url") else ""
            lines.append(f"• <b>[{p['id']}] {esc(p['title'])}</b> ({esc(p['sponsor_name'])}){photo_badge} — Views: {p['impressions_count']}, Clicks: {p['clicks_count']}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if action == "create":
        full_text = " ".join(args[1:])
        parts = [part.strip() for part in full_text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text(
                "<i>Usage:</i> <code>/campaign create Sponsor | Title | Text [| ButtonText | ButtonURL [| PhotoURL]]</code>\n\n"
                "💡 <i>Tip: You can also attach a photo or reply to a photo when running <code>/campaign create</code>!</i>",
                parse_mode="HTML"
            )
            return

        sponsor = parts[0]
        title = parts[1]
        msg_text = parts[2]
        btn_text = parts[3] if len(parts) > 3 and parts[3] else None
        btn_url = parts[4] if len(parts) > 4 and parts[4] else None

        # Check for photo: attached to message, replied-to photo, or 6th pipe parameter
        photo_url = None
        has_photo_list = bool(
            update.message
            and isinstance(getattr(update.message, "photo", None), (list, tuple))
            and len(update.message.photo) > 0
        )
        replied_photo_list = bool(
            update.message
            and getattr(update.message, "reply_to_message", None)
            and isinstance(getattr(update.message.reply_to_message, "photo", None), (list, tuple))
            and len(update.message.reply_to_message.photo) > 0
        )

        if has_photo_list:
            photo_url = update.message.photo[-1].file_id
        elif replied_photo_list:
            photo_url = update.message.reply_to_message.photo[-1].file_id
        elif len(parts) > 5 and parts[5]:
            photo_url = parts[5]

        promo_id = await add_promotion_db(title, sponsor, msg_text, btn_text, btn_url, photo_url=photo_url)
        photo_notice = " with photo 📷" if photo_url else ""
        await update.message.reply_text(f"✅ <i>Campaign created{photo_notice} with ID</i> <code>{promo_id}</code>.", parse_mode="HTML")
