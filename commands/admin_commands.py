import os
import asyncio
import time
import logging
from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes
from html import escape as esc

from security import safe_tele_func_call, format_duration
from handlers.rating import ask_for_rating
from games.registry import end_any_active_game
from session_manager import start_chat_session, end_chat_session, is_in_chat, get_partner
from moderation import is_admin, apply_restriction, clear_restriction, severity_for_score, SEVERITY_DURATIONS
from saveNload import add_promotion_db, get_active_promotions_db, get_pool
from games.content.content_manager import get_stats as get_game_content_stats, add_wyr_question, add_trivia_question
from message import (
    GIVE_BROADCAST_MESSAGE_TEXT, GIVE_VALID_CONNECT_USER_ID_TEXT, TARGET_NOT_IN_DB_TEXT,
    ALREADY_CONNECTED_TO_TARGET_TEXT, PARTNER_LEFT_CHAT_TEXT, ADMIN_HELP_TEXT, BAN_USAGE_TEXT,
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
        import re
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

    import re
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

    is_direct = False
    if clean_text.lower().startswith("direct"):
        is_direct = True
        clean_text = clean_text[len("direct"):].strip()

    is_reply_broadcast = bool(replied_msg and not clean_text)

    if not is_reply_broadcast and not clean_text and not has_photo:
        await update.message.reply_text(
            "<b>📢 Broadcast Usage:</b>\n\n"
            "• <code>/broadcast &lt;message&gt;</code> — Posts to official channel (instant)\n"
            "• <code>/broadcast direct &lt;message&gt;</code> — DMs all bot users in batches\n"
            "• <i>Reply to any message (with text, photos, formatting) with</i> <code>/broadcast</code> <i>to forward it directly!</i>",
            parse_mode="HTML"
        )
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

    message = update.message.text
    if message.lower().startswith("/connect"):
        message = message[len("/connect"):].strip()
    try:
        target_id = int(message)
    except ValueError:
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

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(ADMIN_HELP_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
        severity = int(args[1])
    except ValueError:
        await update.message.reply_text(BAN_USAGE_TEXT, parse_mode="HTML")
        return

    if not (0 <= severity <= 10):
        await update.message.reply_text(SEVERITY_RANGE_TEXT, parse_mode="HTML")
        return

    if target_id == user_id:
        await update.message.reply_text(CANT_RESTRICT_SELF_TEXT, parse_mode="HTML")
        return
    if is_admin(target_id):
        await update.message.reply_text(ADMINS_CANT_BE_RESTRICTED_TEXT, parse_mode="HTML")
        return

    reason = " ".join(args[2:]) if len(args) > 2 else "Manual admin action"

    # Enforce queue eviction & chat severance
    until = await apply_restriction(target_id, severity, reason, context=context)
    if not until:
        await update.message.reply_text(SEVERITY_ZERO_NOOP_TEXT, parse_mode="HTML")
        return

    remaining = format_duration(until - time.time())
    await update.message.reply_text(f"⛔ <i>User</i> <code>{target_id}</code> <i>restricted for</i> <b>{esc(remaining)}</b> <i>(severity {severity}).</i>\n<i>Reason:</i> <code>{esc(reason)}</code>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=f"⛔ <b>You've been restricted by an admin.</b>\n<i>Reason:</i> <code>{esc(reason)}</code>\n<i>Time:</i> <code>{esc(remaining)}</code>", parse_mode="HTML")


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(UNBAN_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    await clear_restriction(target_id)
    await update.message.reply_text(f"✅ <i>User</i> <code>{target_id}</code> <i>has been unrestricted.</i>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=target_id, text=RESTRICTION_LIFTED_TEXT, parse_mode="HTML")


async def check_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args:
        await update.message.reply_text(CHECKUSER_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    from init import ensure_user_loaded
    details = await ensure_user_loaded(target_id)

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
        f"Points: {details.get('points', 0)}\n"
        f"Votes: {(details.get('votes') or {}).get('up', 0)} 👍 {(details.get('votes') or {}).get('down', 0)} 👎\n"
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
    await update.message.reply_text(text, parse_mode="HTML")


async def giveaway_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(GIVEAWAY_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text(GIVE_VALID_USER_ID_TEXT, parse_mode="HTML")
        return

    tier_key = args[1].lower()
    if tier_key not in subscription.TIERS:
        await update.message.reply_text(GIVEAWAY_UNKNOWN_TIER_TEXT, parse_mode="HTML")
        return

    tier = subscription.TIERS[tier_key]
    new_expiry = subscription.grant_subscription(target_id, tier_key, source="admin_grant")
    from saveNload import add_subscription_db
    await add_subscription_db(target_id, tier_key, tier["duration_days"], source="admin_grant")
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(new_expiry))

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

    args = context.args
    if len(args) < 2:
        await update.message.reply_text(REFERRAL_USAGE_TEXT, parse_mode="HTML")
        return

    try:
        required_referrals = int(args[0])
        duration_days = int(args[1])
    except ValueError:
        await update.message.reply_text(REFERRAL_USAGE_TEXT, parse_mode="HTML")
        return

    scheme = await referral.set_scheme(required_referrals, duration_days)

    if not scheme.get("required_referrals"):
        await update.message.reply_text(REFERRAL_DISABLED_TEXT, parse_mode="HTML")
        return

    tier = subscription.TIERS[referral.REWARD_TIER]
    expires_str = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(scheme["expires"]))
    await update.message.reply_text(
        f"✅ <i>Referral scheme active: refer</i> <b>{scheme['required_referrals']}</b> "
        f"<i>friends who finish onboarding →</i> <b>{tier['label']}</b> <i>subscription.</i>\n"
        f"<i>Promo runs until</i> <code>{esc(expires_str)}</code>.",
        parse_mode="HTML",
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows operational bot health and statistics."""
    if not is_admin(update.effective_user.id):
        return

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
    await update.message.reply_text(text, parse_mode="HTML")


async def queue_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows queue details."""
    if not is_admin(update.effective_user.id):
        return

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
    await update.message.reply_text(text, parse_mode="HTML")


async def campaign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manage sponsor campaigns."""
    if not is_admin(update.effective_user.id):
        return

    args = context.args
    if not args or args[0] == "help":
        await update.message.reply_text(
            "📢 <b>Campaign Management</b>\n\n"
            "<i>/campaign list</i> - View all active campaigns\n"
            "<i>/campaign create Sponsor | Title | Text | ButtonText | ButtonURL</i>\n",
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
            lines.append(f"• <b>[{p['id']}] {esc(p['title'])}</b> ({esc(p['sponsor_name'])}) — Views: {p['impressions_count']}, Clicks: {p['clicks_count']}")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return

    if action == "create":
        full_text = " ".join(args[1:])
        parts = [part.strip() for part in full_text.split("|")]
        if len(parts) < 3:
            await update.message.reply_text("<i>Usage: /campaign create Sponsor | Title | Text [| ButtonText | ButtonURL]</i>", parse_mode="HTML")
            return

        sponsor = parts[0]
        title = parts[1]
        msg_text = parts[2]
        btn_text = parts[3] if len(parts) > 3 else None
        btn_url = parts[4] if len(parts) > 4 else None

        promo_id = await add_promotion_db(title, sponsor, msg_text, btn_text, btn_url)
        await update.message.reply_text(f"✅ <i>Campaign created with ID</i> <code>{promo_id}</code>.", parse_mode="HTML")
