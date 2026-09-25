"""
Daily Chat Streaks & Extended Rewards Engine for AnonChatZoneBot.

Tracks consecutive daily chat activity, maintains current and longest streaks,
and unlocks escalating rewards and VIP subscriptions at major milestones:
- Day 3: +50 credits / bonus points
- Day 7: 1 Day VIP Access
- Day 30: 1 Week VIP Access (7 Days)
- Day 60: 2 Weeks VIP Access (14 Days)
- Day 120: 3 Weeks VIP Access (21 Days)
- Day 240: 4 Weeks VIP Access (28 Days)
- Day 480: 5 Weeks VIP Access (35 Days)
- Day 960: 6 Weeks VIP Access (42 Days)
"""

import logging
import time
from datetime import datetime, date, timezone, timedelta
from typing import Dict, Any, Optional, Tuple

import init
from subscription import grant_vip_days
from security import safe_tele_func_call

logger = logging.getLogger(__name__)

STREAK_REWARDS: Dict[int, Dict[str, Any]] = {
    3: {
        "type": "credits",
        "amount": 50,
        "label": "50 Bonus Points / Credits",
    },
    7: {
        "type": "vip",
        "days": 1,
        "tier": "daily",
        "label": "1 Day VIP Access",
    },
    30: {
        "type": "vip",
        "days": 7,
        "tier": "weekly",
        "label": "1 Week VIP Access",
    },
    60: {
        "type": "vip",
        "days": 14,
        "tier": "weekly",
        "label": "2 Weeks VIP Access",
    },
    120: {
        "type": "vip",
        "days": 21,
        "tier": "weekly",
        "label": "3 Weeks VIP Access",
    },
    240: {
        "type": "vip",
        "days": 28,
        "tier": "weekly",
        "label": "4 Weeks VIP Access",
    },
    480: {
        "type": "vip",
        "days": 35,
        "tier": "weekly",
        "label": "5 Weeks VIP Access",
    },
    960: {
        "type": "vip",
        "days": 42,
        "tier": "weekly",
        "label": "6 Weeks VIP Access",
    },
}


def get_next_streak_milestone(current_streak: int) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
    """Returns the next unreached streak milestone (day_number, reward_info) or (None, None)."""
    for day in sorted(STREAK_REWARDS.keys()):
        if day > current_streak:
            return day, STREAK_REWARDS[day]
    return None, None


def get_streak_info(user_id: int) -> Dict[str, Any]:
    """Returns comprehensive streak statistics for the given user."""
    user = init.user_details.get(user_id, {})
    current = user.get("current_streak", 0) or 0
    longest = user.get("longest_streak", 0) or 0
    last_date = user.get("last_streak_date")
    claimed = user.get("streak_rewards_claimed", []) or []
    next_day, next_rew = get_next_streak_milestone(current)

    return {
        "current_streak": current,
        "longest_streak": longest,
        "last_streak_date": last_date,
        "streak_rewards_claimed": claimed,
        "next_milestone_day": next_day,
        "next_milestone_reward": next_rew,
    }


def update_streak_on_chat(
    user_id: int, target_date: Optional[date] = None
) -> Tuple[int, bool, Optional[Dict[str, Any]]]:
    """
    Updates user streak progress upon completing an active, meaningful chat session.
    
    Returns:
        (new_streak, was_incremented, milestone_reward_unlocked_or_None)
    """
    if user_id not in init.user_details:
        init.user_details[user_id] = init._default_user()
    user = init.user_details[user_id]

    today = target_date or datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)

    last_date_str = user.get("last_streak_date")
    last_date = None
    if last_date_str:
        try:
            last_date = datetime.strptime(str(last_date_str), "%Y-%m-%d").date()
        except ValueError:
            last_date = None

    current = user.get("current_streak", 0) or 0
    claimed = user.setdefault("streak_rewards_claimed", [])

    # Already recorded for today
    if last_date == today:
        return current, False, None

    if last_date == yesterday:
        new_streak = current + 1
    else:
        # Missed a day or first chat ever
        new_streak = 1

    longest = max(user.get("longest_streak", 0) or 0, new_streak)

    user["current_streak"] = new_streak
    user["longest_streak"] = longest
    user["last_streak_date"] = str(today)
    init.dirty_users.add(user_id)

    # Check for unlocked milestone reward
    unlocked_reward = None
    if new_streak in STREAK_REWARDS and new_streak not in claimed:
        unlocked_reward = STREAK_REWARDS[new_streak]

    return new_streak, True, unlocked_reward


async def claim_milestone_reward(bot, user_id: int, milestone: int, reward: Dict[str, Any]):
    """
    Applies streak milestone rewards (points or VIP days) and sends a congratulatory Telegram message.
    """
    if user_id not in init.user_details:
        await init.ensure_user_loaded(user_id)
    user = init.user_details.get(user_id, {})
    claimed = user.setdefault("streak_rewards_claimed", [])

    if milestone in claimed:
        return

    claimed.append(milestone)
    init.dirty_users.add(user_id)

    reward_type = reward.get("type")
    if reward_type == "credits":
        amount = reward.get("amount", 0)
        user["points"] = user.get("points", 0) + amount
    elif reward_type == "vip":
        days = reward.get("days", 1)
        tier = reward.get("tier", "weekly")
        grant_vip_days(user_id, days=days, tier_key=tier, source="streak_reward")
        try:
            from saveNload import add_subscription_db
            await add_subscription_db(user_id, tier=tier, duration_days=days, source="streak_reward")
        except Exception as e:
            logger.warning(f"Error persisting subscription for streak reward: {e}")

    # Notify user of their achievement
    congrats_text = (
        "🔥 <b>Chat Streak Milestone Unlocked!</b> 🔥\n\n"
        f"Incredible dedication! You have reached a <b>{milestone}-Day Chat Streak</b>!\n\n"
        f"🎁 <b>Reward Received:</b> <i>{reward.get('label', '')}</i>\n\n"
        "<i>Keep chatting every day to unlock even bigger rewards!</i> 🚀"
    )

    if bot:
        await safe_tele_func_call(
            bot.send_message,
            chat_id=user_id,
            text=congrats_text,
            parse_mode="HTML"
        )
