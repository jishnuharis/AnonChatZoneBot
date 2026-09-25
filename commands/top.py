"""
Weekly Leaderboard (/top, /leaderboard) for AnonChatZoneBot.

Displays anonymized rankings with Telegram blockquote styling:
- Top Streaks (🔥)
- Karma & Upvotes (⭐)
- Mini-Games & Points (🎮)

Features weekly reset timer, top 3 podium medals, and personalized standing cards.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import init
from handlers.setup import check_user_profile
from security import safe_tele_func_call

logger = logging.getLogger(__name__)

RANK_ICONS = {
    1: "🥇",
    2: "🥈",
    3: "🥉",
}
DEFAULT_RANK_ICON = "🎖️⭐"


def anonymize_id(user_id: int) -> str:
    """Anonymizes user ID into 6286*** pattern matching UI specifications."""
    s = str(user_id)
    if len(s) >= 4:
        return f"{s[:4]}***"
    return f"{s}***"


def get_weekly_reset_countdown() -> Tuple[int, int]:
    """Returns (days_left, hours_left) until next Sunday 23:59:59 UTC."""
    now = datetime.now(timezone.utc)
    days_ahead = 6 - now.weekday()
    if days_ahead < 0:
        days_ahead += 7
    target_sunday = (now + timedelta(days=days_ahead)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )
    diff = target_sunday - now
    total_hours = max(0, int(diff.total_seconds() // 3600))
    days = total_hours // 24
    hours = total_hours % 24
    return days, hours


async def fetch_leaderboard(category: str, viewer_id: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Fetches top 10 rankings and the viewer's personal stats for the chosen category.
    Uses PostgreSQL pool when available with fallback to in-memory cache.
    """
    from saveNload import is_pool_ready, get_pool
    from psycopg.rows import dict_row

    top_list: List[Dict[str, Any]] = []
    viewer_stats: Dict[str, Any] = {"rank": None, "score": 0, "total_users": 0}

    # In-memory fallback builder
    def _from_memory():
        nonlocal top_list, viewer_stats
        records = []
        for uid, details in init.user_details.items():
            if not isinstance(details, dict) or details.get("is_banned"):
                continue
            if category == "streaks":
                c_st = details.get("current_streak", 0) or 0
                l_st = details.get("longest_streak", 0) or 0
                if c_st > 0:
                    records.append({"user_id": uid, "score": c_st, "extra": l_st})
            elif category == "karma":
                votes = details.get("votes", {})
                up = votes.get("up", 0) if isinstance(votes, dict) else 0
                if up > 0:
                    records.append({"user_id": uid, "score": up, "extra": 0})
            elif category == "games":
                pts = details.get("points", 0) or 0
                if pts > 0:
                    records.append({"user_id": uid, "score": pts, "extra": 0})

        if category == "streaks":
            records.sort(key=lambda r: (r["score"], r["extra"]), reverse=True)
        else:
            records.sort(key=lambda r: r["score"], reverse=True)

        top_list = records[:10]
        viewer_score = 0
        v_details = init.user_details.get(viewer_id, {})
        if category == "streaks":
            viewer_score = v_details.get("current_streak", 0) or 0
        elif category == "karma":
            v_votes = v_details.get("votes", {})
            viewer_score = v_votes.get("up", 0) if isinstance(v_votes, dict) else 0
        elif category == "games":
            viewer_score = v_details.get("points", 0) or 0

        viewer_rank = None
        for idx, rec in enumerate(records, start=1):
            if rec["user_id"] == viewer_id:
                viewer_rank = idx
                break
        if viewer_rank is None and viewer_score > 0:
            viewer_rank = len(records) + 1

        viewer_stats = {
            "rank": viewer_rank,
            "score": viewer_score,
            "total_users": max(len(records), 1),
        }

    if not is_pool_ready():
        _from_memory()
        return top_list, viewer_stats

    try:
        p = get_pool()
        async with p.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                if category == "streaks":
                    await cur.execute("""
                        SELECT u.user_id, p.current_streak as score, p.longest_streak as extra
                        FROM user_profiles p
                        JOIN users u ON p.user_id = u.user_id
                        WHERE p.is_banned = FALSE AND p.current_streak > 0
                        ORDER BY p.current_streak DESC, p.longest_streak DESC, u.user_id ASC
                        LIMIT 10;
                    """)
                    top_list = await cur.fetchall()

                    # Viewer stats
                    await cur.execute("SELECT current_streak FROM user_profiles WHERE user_id = %s;", (viewer_id,))
                    row = await cur.fetchone()
                    v_score = row["current_streak"] if row and row["current_streak"] else 0

                    await cur.execute("""
                        SELECT COUNT(*) + 1 as rank FROM user_profiles
                        WHERE is_banned = FALSE AND current_streak > %s;
                    """, (v_score,))
                    rank_row = await cur.fetchone()
                    v_rank = rank_row["rank"] if v_score > 0 and rank_row else None

                    await cur.execute("SELECT COUNT(*) as total FROM user_profiles WHERE current_streak > 0;")
                    tot_row = await cur.fetchone()
                    total = tot_row["total"] if tot_row else 1

                    viewer_stats = {"rank": v_rank, "score": v_score, "total_users": total}

                elif category == "karma":
                    await cur.execute("""
                        SELECT target_id as user_id, COUNT(*) as score, 0 as extra
                        FROM user_ratings
                        WHERE vote_type = 'up'
                        GROUP BY target_id
                        ORDER BY score DESC
                        LIMIT 10;
                    """)
                    top_list = await cur.fetchall()

                    await cur.execute("SELECT COUNT(*) as score FROM user_ratings WHERE target_id = %s AND vote_type = 'up';", (viewer_id,))
                    row = await cur.fetchone()
                    v_score = row["score"] if row else 0

                    v_rank = None
                    if v_score > 0:
                        await cur.execute("""
                            SELECT COUNT(*) + 1 as rank FROM (
                                SELECT target_id, COUNT(*) as up_count
                                FROM user_ratings WHERE vote_type = 'up'
                                GROUP BY target_id HAVING COUNT(*) > %s
                            ) sub;
                        """, (v_score,))
                        rr = await cur.fetchone()
                        v_rank = rr["rank"] if rr else None

                    viewer_stats = {"rank": v_rank, "score": v_score, "total_users": max(len(top_list), 1)}

                elif category == "games":
                    await cur.execute("""
                        SELECT user_id, points as score, 0 as extra
                        FROM users
                        WHERE points > 0
                        ORDER BY points DESC
                        LIMIT 10;
                    """)
                    top_list = await cur.fetchall()

                    await cur.execute("SELECT points FROM users WHERE user_id = %s;", (viewer_id,))
                    row = await cur.fetchone()
                    v_score = row["points"] if row and row["points"] else 0

                    v_rank = None
                    if v_score > 0:
                        await cur.execute("SELECT COUNT(*) + 1 as rank FROM users WHERE points > %s;", (v_score,))
                        rr = await cur.fetchone()
                        v_rank = rr["rank"] if rr else None

                    viewer_stats = {"rank": v_rank, "score": v_score, "total_users": max(len(top_list), 1)}

    except Exception as e:
        logger.warning(f"Error executing leaderboard query: {e}. Falling back to memory.")
        _from_memory()

    return top_list, viewer_stats


def _build_keyboard(current_cat: str) -> InlineKeyboardMarkup:
    """Builds category tab buttons and refresh control."""
    cats = [
        ("streaks", "🔥 Streaks"),
        ("karma", "⭐ Karma"),
        ("games", "🎮 Mini-Games"),
    ]
    row1 = []
    for key, label in cats:
        btn_text = f"{label} ✅" if key == current_cat else label
        row1.append(InlineKeyboardButton(btn_text, callback_data=f"top|{key}"))
    row2 = [InlineKeyboardButton("🔄 Refresh", callback_data=f"top|{current_cat}")]
    return InlineKeyboardMarkup([row1, row2])


async def render_leaderboard_text(category: str, viewer_id: int) -> str:
    """Renders the HTML text for the leaderboard with Telegram blockquote tags."""
    days_left, hours_left = get_weekly_reset_countdown()
    top_list, stats = await fetch_leaderboard(category, viewer_id)

    title_map = {
        "streaks": "🔥 Daily Chat Streaks (Top 10)",
        "karma": "⭐ Karma & Upvotes Leaderboard (Top 10)",
        "games": "🎮 Mini-Games & Points (Top 10)",
    }
    cat_title = title_map.get(category, "🏆 Chat Zone Leaderboard")

    # Build top 10 blockquote lines
    lines = []
    for rank, entry in enumerate(top_list, start=1):
        icon = RANK_ICONS.get(rank, DEFAULT_RANK_ICON)
        anon = anonymize_id(entry["user_id"])
        score = entry["score"]
        if category == "streaks":
            best = entry.get("extra", score)
            lines.append(f"{icon} <b>{anon}</b>: <b>{score} days</b> <i>(Best: {best}d)</i>")
        elif category == "karma":
            lines.append(f"{icon} <b>{anon}</b>: <b>{score} 👍</b>")
        elif category == "games":
            lines.append(f"{icon} <b>{anon}</b>: <b>{score:,} pts</b>")

    if not lines:
        lines.append("<i>No records yet for this weekly cycle. Be the first!</i>")

    top_blockquote = "<blockquote>\n" + "\n".join(lines) + "\n</blockquote>"

    # Build viewer standing card
    v_rank = stats.get("rank")
    v_score = stats.get("score", 0)
    cutoff_score = top_list[-1]["score"] if len(top_list) >= 10 else (top_list[-1]["score"] if top_list else 0)

    stats_lines = []
    if v_score <= 0:
        if category == "streaks":
            stats_lines.append("<i>You haven't started a chat streak yet.</i>")
            gap = (cutoff_score + 1) if cutoff_score > 0 else 1
            stats_lines.append(f"<i>(You need {gap} streak days to enter the Top 10)</i>")
        elif category == "karma":
            stats_lines.append("<i>You haven't received any upvotes yet.</i>")
            gap = (cutoff_score + 1) if cutoff_score > 0 else 1
            stats_lines.append(f"<i>(You need {gap} upvotes to enter the Top 10)</i>")
        elif category == "games":
            stats_lines.append("<i>You haven't played any battles yet.</i>")
            gap = (cutoff_score + 1) if cutoff_score > 0 else 1
            stats_lines.append(f"<i>(You need {gap:,} points to enter the Top 10)</i>")
    else:
        rank_str = f"#{v_rank}" if v_rank else "Unranked"
        if category == "streaks":
            stats_lines.append(f"Rank: <b>{rank_str}</b> | 🔥 <b>{v_score} days streak</b>")
            if v_rank and v_rank > 10 and cutoff_score > v_score:
                diff = cutoff_score - v_score + 1
                stats_lines.append(f"<i>(You need {diff} more streak days to enter the Top 10)</i>")
            elif v_rank and v_rank <= 10:
                stats_lines.append("🎉 <i>You are currently in the Top 10! Keep it up!</i>")
        elif category == "karma":
            stats_lines.append(f"Rank: <b>{rank_str}</b> | ⭐ <b>{v_score} Upvotes</b>")
            if v_rank and v_rank > 10 and cutoff_score > v_score:
                diff = cutoff_score - v_score + 1
                stats_lines.append(f"<i>(You need {diff} more upvotes to enter the Top 10)</i>")
            elif v_rank and v_rank <= 10:
                stats_lines.append("🎉 <i>You are currently in the Top 10!</i>")
        elif category == "games":
            stats_lines.append(f"Rank: <b>{rank_str}</b> | <b>{v_score:,} pts</b>")
            if v_rank and v_rank > 10 and cutoff_score > v_score:
                diff = cutoff_score - v_score + 1
                stats_lines.append(f"<i>(You need {diff:,} points to enter the Top 10)</i>")
            elif v_rank and v_rank <= 10:
                stats_lines.append("🎉 <i>You are currently in the Top 10!</i>")

    user_blockquote = "<blockquote>\n<b>Your Stats:</b>\n" + "\n".join(stats_lines) + "\n</blockquote>"

    header = (
        f"🏆 <b>{cat_title}</b>\n"
        f"⏳ <i>Weekly reset in {days_left}d {hours_left}h — Top 3 win <b>Free VIP</b>!</i> 🎁\n\n"
    )

    return f"{header}{top_blockquote}\n{user_blockquote}"


@check_user_profile
async def show_top_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles /top and /leaderboard commands."""
    user_id = update.effective_user.id
    category = "streaks"
    text = await render_leaderboard_text(category, user_id)
    keyboard = _build_keyboard(category)

    if update.message:
        await safe_tele_func_call(
            update.message.reply_text,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


async def handle_top_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles tab switching and refreshing for the leaderboard."""
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    parts = query.data.split("|")
    category = parts[1] if len(parts) > 1 else "streaks"
    if category not in ("streaks", "karma", "games"):
        category = "streaks"

    user_id = update.effective_user.id
    text = await render_leaderboard_text(category, user_id)
    keyboard = _build_keyboard(category)

    await safe_tele_func_call(
        query.edit_message_text,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
