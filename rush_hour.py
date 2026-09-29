"""
Rush Hour Event Management Module
Automatically triggers Friday & Saturday 8:00 PM – 10:00 PM IST (UTC+5:30).

Features:
- Scheduled start and end jobs via JobQueue (APScheduler).
- Broadcasts announcement to users in rate-limited batches and to the official channel.
- The first 5 unique users to execute /find during Rush Hour unlock 1 hour of Free VIP Premium!
- Admin command /rushhour (status, start, end, test).
"""
import asyncio
import logging
import os
import random
from typing import Set

from telegram import Update
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call, safe_reply
from subscription import grant_vip_hours
from moderation import is_admin

logger = logging.getLogger(__name__)

# State
_is_active: bool = False
_claimed_user_ids: Set[int] = set()
MAX_REWARD_WINNERS = 5

RUSH_HOUR_START_TEXT = (
    "🔥 <b>WEEKEND RUSH HOUR IS LIVE!</b> (8:00 PM – 10:00 PM IST) ⚡\n\n"
    "Queues are full and wait times are zero! Everyone is chatting right now.\n\n"
    "🎁 <b>SPEED BONUS:</b> The first 5 users to tap /find right now unlock "
    "<b>1 HOUR OF FREE VIP PREMIUM</b>! 👑\n\n"
    "👉 Tap /find to claim your spot and chat!"
)

RUSH_HOUR_END_TEXT = (
    "🌙 <b>Weekend Rush Hour has ended!</b>\n\n"
    "Thanks to everyone who joined the chats tonight. Catch you in the next Rush Hour! 💬"
)

RUSH_HOUR_WINNER_NOTIFICATION = (
    "🎉 <b>BOOM! You're one of the first 5 users!</b> ⚡\n\n"
    "You've unlocked <b>1 Hour of Free VIP Premium</b> for tonight's Rush Hour! 👑\n"
    "• Unlimited skips (/next)\n"
    "• Priority matchmaking\n"
    "• Unlimited voice calls & media\n\n"
    "Enjoy your chat session! 💬"
)


def is_rush_hour_active() -> bool:
    """Returns True if Rush Hour is currently active."""
    return _is_active


def set_rush_hour_active(active: bool):
    """Sets active state and resets claims when deactivated."""
    global _is_active
    _is_active = active
    if not active:
        _claimed_user_ids.clear()


def get_claimed_count() -> int:
    """Returns count of users who claimed the 1-hour VIP during the current session."""
    return len(_claimed_user_ids)


def claim_rush_hour_reward(user_id: int) -> bool:
    """
    Attempts to claim the 1-hour VIP reward for the user.
    Returns True if successfully claimed, False otherwise.
    """
    global _claimed_user_ids
    if not _is_active:
        return False
    if user_id in _claimed_user_ids:
        return False
    if len(_claimed_user_ids) >= MAX_REWARD_WINNERS:
        return False

    _claimed_user_ids.add(user_id)
    grant_vip_hours(user_id, hours=1.0, source="rush_hour")
    logger.info(
        f"User {user_id} claimed Rush Hour 1-hour VIP reward! "
        f"({len(_claimed_user_ids)}/{MAX_REWARD_WINNERS})"
    )
    return True


async def broadcast_rush_hour(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Safely broadcasts Rush Hour announcements in randomized parallel chunks to users and official channel."""
    # 1. Post to official channel if configured
    channel_id = os.getenv("ANNOUNCEMENT_CHANNEL", getattr(init, "ANNOUNCEMENT_CHANNEL", "@channelofchatzone"))
    if channel_id and channel_id.strip():
        try:
            await safe_tele_func_call(
                context.bot.send_message,
                chat_id=channel_id,
                text=message_text,
                parse_mode="HTML"
            )
            logger.info(f"Posted Rush Hour notice to channel {channel_id}")
        except Exception as e:
            logger.warning(f"Could not post Rush Hour notice to channel: {e}")

    # 2. Shuffle target users for complete fairness across broadcasts
    target_users = list(init.user_details.keys())
    random.shuffle(target_users)

    batch_size = 20
    sent = 0

    for i in range(0, len(target_users), batch_size):
        chunk = target_users[i:i + batch_size]
        tasks = [
            safe_tele_func_call(
                context.bot.send_message,
                chat_id=uid,
                text=message_text,
                parse_mode="HTML"
            )
            for uid in chunk
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if r and not isinstance(r, Exception):
                sent += 1

        # Pause to respect Telegram's 30 msg/sec global broadcast limit
        await asyncio.sleep(0.8)

    logger.info(f"Rush Hour broadcast completed: sent to {sent}/{len(target_users)} users.")


async def start_rush_hour_job(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled callback: Starts Rush Hour every Friday & Saturday at 8:00 PM IST."""
    global _is_active
    _is_active = True
    _claimed_user_ids.clear()
    logger.info("🔥 Rush Hour started!")
    await broadcast_rush_hour(context, RUSH_HOUR_START_TEXT)


async def end_rush_hour_job(context: ContextTypes.DEFAULT_TYPE):
    """Scheduled callback: Ends Rush Hour at 10:00 PM IST."""
    global _is_active
    if not _is_active:
        return
    _is_active = False
    _claimed_user_ids.clear()
    logger.info("🌙 Rush Hour ended.")


async def rush_hour_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Admin command to inspect or control Rush Hour manually.
    Usage:
      /rushhour        - Show status
      /rushhour start  - Trigger Rush Hour now (with broadcast)
      /rushhour end    - End Rush Hour now
      /rushhour test   - Simulate claiming the 1-hr VIP reward
    """
    user_id = update.effective_user.id if update.effective_user else 0
    if not is_admin(user_id):
        return

    args = context.args or []
    subcmd = args[0].lower() if args else "status"

    if subcmd == "start":
        await start_rush_hour_job(context)
        await safe_reply(
            update,
            text=f"🔥 <b>Rush Hour manually started!</b> Broadcast sent to users.\nClaimed: 0/{MAX_REWARD_WINNERS}",
            context=context,
        )
    elif subcmd == "end":
        await end_rush_hour_job(context)
        await safe_reply(
            update,
            text="🌙 <b>Rush Hour manually ended!</b>",
            context=context,
        )
    elif subcmd == "test":
        set_rush_hour_active(True)
        claimed = claim_rush_hour_reward(user_id)
        if claimed:
            await safe_reply(
                update,
                text=RUSH_HOUR_WINNER_NOTIFICATION,
                context=context,
            )
        else:
            await safe_reply(
                update,
                text=f"⚠️ Could not claim: already claimed or limit reached ({get_claimed_count()}/{MAX_REWARD_WINNERS}).",
                context=context,
            )
    else:
        status_str = "🟢 ACTIVE" if _is_active else "🔴 INACTIVE"
        await safe_reply(
            update,
            text=(
                f"<b>⚡ Rush Hour Status:</b> {status_str}\n"
                f"<b>Claimed Rewards:</b> {get_claimed_count()}/{MAX_REWARD_WINNERS}\n"
                f"<b>Schedule:</b> Fridays & Saturdays, 8:00 PM – 10:00 PM IST\n\n"
                f"<i>Admin controls:</i>\n"
                f"• <code>/rushhour start</code> — Manually activate & broadcast\n"
                f"• <code>/rushhour end</code> — Manually deactivate\n"
                f"• <code>/rushhour test</code> — Test claim reward for yourself"
            ),
            context=context,
        )
