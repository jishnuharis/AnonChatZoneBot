"""
Trivia Duel Mini-Game for AnonChatZoneBot.

A competitive 5-round trivia quiz between two anonymous chat partners.
Features data-driven questions across multiple categories, 4 multiple-choice
options, real-time score tracking, and in-bot points awards.
"""

import uuid
import logging
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from games.content.content_manager import get_trivia_questions
from message import PARTNER_LEFT_GAME_TEXT, GAME_ENDED_INACTIVITY_TEXT

import init

logger = logging.getLogger(__name__)

games: Dict[str, Dict[str, Any]] = {}
user_to_session: Dict[int, str] = {}

TIMEOUT = 120
GAME_TYPE = "trivia"
TOTAL_ROUNDS = 5
OPTION_LABELS = ["🅰️", "🅱️", "🅲", "🅳"]


def create_session(user1: int, user2: int) -> str:
    session_id = str(uuid.uuid4())
    questions = get_trivia_questions(limit=TOTAL_ROUNDS)

    games[session_id] = {
        "players": [user1, user2],
        "questions": questions,
        "round": 0,
        "scores": {user1: 0, user2: 0},
        "choices": {},
        "messages": {},
        "active": True,
        "timeout_job": None,
    }
    user_to_session[user1] = session_id
    user_to_session[user2] = session_id
    registry.register(user1, GAME_TYPE)
    registry.register(user2, GAME_TYPE)
    return session_id


def get_session(user_id: int):
    return user_to_session.get(user_id)


def _build_keyboard(options: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, opt in enumerate(options):
        label = f"{OPTION_LABELS[i]} {opt}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"trivia|{i}")])
    return InlineKeyboardMarkup(buttons)


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id: str):
    game = games.get(session_id)
    if not game:
        return
    if game["round"] >= len(game["questions"]):
        await _end_game(context, session_id)
        return

    q = game["questions"][game["round"]]
    game["choices"] = {}
    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})

    markup = _build_keyboard(q["options"])
    round_num = game["round"] + 1
    total_rounds = len(game["questions"])

    for user in game["players"]:
        opp = registry.other_player(game, user)
        opp_score = game["scores"].get(opp, 0)
        user_score = game["scores"].get(user, 0)

        text = (
            f"🧠 <b>Trivia Duel</b> — Round {round_num}/{total_rounds}\n"
            f"<i>Category:</i> <b>{q.get('category', 'General')}</b>\n\n"
            f"❓ <b>{q['question']}</b>\n\n"
            f"<i>Score:</i> You <b>{user_score}</b> — Opponent <b>{opp_score}</b>"
        )
        msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, reply_markup=markup, parse_mode="HTML")
        if msg:
            game["messages"][user] = msg.message_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data.split("|")
    if len(data) < 2:
        return
    try:
        pick = int(data[1])
    except ValueError:
        return

    session_id = get_session(user_id)
    if not session_id:
        return
    game = games.get(session_id)
    if not game or not game["active"]:
        return
    if user_id in game["choices"]:
        return

    msg_id = game["messages"].pop(user_id, None)
    q = game["questions"][game["round"]]
    picked_text = q["options"][pick]

    if msg_id:
        await safe_tele_func_call(
            context.bot.edit_message_text,
            chat_id=user_id,
            message_id=msg_id,
            text=f"<i>You locked in:</i> <b>{OPTION_LABELS[pick]} {picked_text}</b>\n<i>Waiting for your partner...</i>",
            parse_mode="HTML"
        )

    game["choices"][user_id] = pick
    other = registry.other_player(game, user_id)
    if other is None:
        return

    if len(game["choices"]) < 2:
        return

    # Both players answered! Resolve round
    correct_idx = q["correct_index"]
    correct_text = q["options"][correct_idx]

    for user in game["players"]:
        user_pick = game["choices"][user]
        is_correct = (user_pick == correct_idx)
        if is_correct:
            game["scores"][user] += 1

    for user in game["players"]:
        user_pick = game["choices"][user]
        opp = registry.other_player(game, user)
        opp_pick = game["choices"][opp]

        my_status = "✅ <b>Correct!</b> (+1 pt)" if user_pick == correct_idx else "❌ <b>Incorrect!</b>"
        opp_status = "got it right ✅" if opp_pick == correct_idx else "missed it ❌"

        summary = (
            f"💡 <i>Correct answer:</i> <b>{OPTION_LABELS[correct_idx]} {correct_text}</b>\n\n"
            f"{my_status}\n"
            f"<i>Your opponent {opp_status}.</i>\n\n"
            f"<b>Current Score:</b> You {game['scores'][user]} — Opponent {game['scores'][opp]}"
        )
        await safe_tele_func_call(context.bot.send_message, chat_id=user, text=summary, parse_mode="HTML")

    game["round"] += 1
    await send_round(context, session_id)


async def _end_game(context: ContextTypes.DEFAULT_TYPE, session_id: str):
    game = games.get(session_id)
    if not game:
        return
    u1, u2 = game["players"]
    s1, s2 = game["scores"][u1], game["scores"][u2]

    if s1 > s2:
        winner, loser = u1, u2
        init.user_details.setdefault(winner, init._default_user())["points"] += 8
        init.dirty_users.add(winner)
        m_win = f"🏆 <b>Trivia Champion!</b> You won {s1} to {s2} (+8 points) 🎉"
        m_lose = f"😔 <b>Match over!</b> Your partner won {s1} to {s2}. Rematch sometime?"
        await safe_tele_func_call(context.bot.send_message, chat_id=winner, text=m_win, parse_mode="HTML")
        await safe_tele_func_call(context.bot.send_message, chat_id=loser, text=m_lose, parse_mode="HTML")
    elif s2 > s1:
        winner, loser = u2, u1
        init.user_details.setdefault(winner, init._default_user())["points"] += 8
        init.dirty_users.add(winner)
        m_win = f"🏆 <b>Trivia Champion!</b> You won {s2} to {s1} (+8 points) 🎉"
        m_lose = f"😔 <b>Match over!</b> Your partner won {s2} to {s1}. Rematch sometime?"
        await safe_tele_func_call(context.bot.send_message, chat_id=winner, text=m_win, parse_mode="HTML")
        await safe_tele_func_call(context.bot.send_message, chat_id=loser, text=m_lose, parse_mode="HTML")
    else:
        init.user_details.setdefault(u1, init._default_user())["points"] += 3
        init.user_details.setdefault(u2, init._default_user())["points"] += 3
        init.dirty_users.update([u1, u2])
        draw_text = f"🤝 <b>It's a draw!</b> Tied {s1} to {s2}. (+3 points each)"
        await safe_tele_func_call(context.bot.send_message, chat_id=u1, text=draw_text, parse_mode="HTML")
        await safe_tele_func_call(context.bot.send_message, chat_id=u2, text=draw_text, parse_mode="HTML")

    _teardown(game, session_id)


async def force_end_game(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    session_id = get_session(user_id)
    if not session_id:
        registry.unregister(user_id)
        return
    game = games.get(session_id)
    if not game:
        registry.unregister(user_id)
        return
    other = registry.other_player(game, user_id)
    if other is not None:
        await safe_tele_func_call(context.bot.send_message, chat_id=other, text=PARTNER_LEFT_GAME_TEXT, parse_mode="HTML")
        init.user_details.setdefault(other, init._default_user())["points"] += 5
        init.dirty_users.add(other)
    _teardown(game, session_id)


def remove_timeout_job(g: dict):
    job = g.get("timeout_job")
    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass
    g["timeout_job"] = None


def _teardown(game: dict, session_id: str):
    remove_timeout_job(game)
    game["active"] = False
    for user in game["players"]:
        user_to_session.pop(user, None)
        registry.unregister(user)
    games.pop(session_id, None)


async def timeout_job(context: ContextTypes.DEFAULT_TYPE):
    session_id = context.job.data["session_id"]
    game = games.get(session_id)
    if not game or not game["active"]:
        return
    for user in game["players"]:
        await safe_tele_func_call(context.bot.send_message, chat_id=user, text=GAME_ENDED_INACTIVITY_TEXT, parse_mode="HTML")
    _teardown(game, session_id)
