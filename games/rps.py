from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from message import (
    OPPONENT_ALREADY_PICKED_TEXT, PARTNER_LEFT_GAME_TEXT, GAME_ENDED_INACTIVITY_TEXT,
    WON_MATCH_TEXT, LOST_MATCH_TEXT,
)

import uuid

import init

games = {}
user_to_session = {}

TIMEOUT = 180
GAME_TYPE = "rps"
WINS_NEEDED = 3

EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


def create_session(user1, user2):
    session_id = str(uuid.uuid4())
    games[session_id] = {
        "players": [user1, user2],
        "choices": {},
        "score": {user1: 0, user2: 0},
        "round": 1,
        "messages": {},
        "active": True,
        "timeout_job": None,
    }
    user_to_session[user1] = session_id
    user_to_session[user2] = session_id
    registry.register(user1, GAME_TYPE)
    registry.register(user2, GAME_TYPE)
    return session_id


def get_session(user_id):
    return user_to_session.get(user_id)


def _keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🪨 Rock", callback_data="rps|rock"),
        InlineKeyboardButton("📄 Paper", callback_data="rps|paper"),
        InlineKeyboardButton("✂️ Scissors", callback_data="rps|scissors"),
    ]])


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})
    game["messages"].clear()

    for user in game["players"]:
        s1 = game["score"][user]
        opp = registry.other_player(game, user)
        s2 = game["score"][opp] if opp is not None else 0
        text = f"🪨📄✂️ <b>Rock Paper Scissors</b> — Round {game['round']}\n<i>Score:</i> You <b>{s1}</b> — Opponent <b>{s2}</b>\n<i>First to {WINS_NEEDED} wins.</i>"
        msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, reply_markup=_keyboard(), parse_mode="HTML")
        if msg:
            game["messages"][user] = msg.message_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    choice = query.data.split("|")[1]

    session_id = get_session(user_id)
    if not session_id:
        return
    game = games.get(session_id)
    if not game or not game["active"]:
        return
    if user_id in game["choices"]:
        return

    msg_id = game["messages"].pop(user_id, None)
    if msg_id:
        await safe_tele_func_call(context.bot.edit_message_text, chat_id=user_id, message_id=msg_id, text=f"<i>Locked in:</i> {EMOJI[choice]}", parse_mode="HTML")

    game["choices"][user_id] = choice
    other = registry.other_player(game, user_id)

    if len(game["choices"]) == 1:
        if other is not None:
            await safe_tele_func_call(context.bot.send_message, chat_id=other, text=OPPONENT_ALREADY_PICKED_TEXT, parse_mode="HTML")
        return

    await _resolve(context, session_id)


async def _resolve(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    u1, u2 = game["players"]
    c1, c2 = game["choices"][u1], game["choices"][u2]

    if c1 == c2:
        outcome = f"<i>Both picked</i> {EMOJI[c1]}. <i>It's a tie, replaying this round!</i>"
        winner = None
    elif BEATS[c1] == c2:
        winner = u1
        outcome = f"{EMOJI[c1]} <i>beats</i> {EMOJI[c2]}!"
    else:
        winner = u2
        outcome = f"{EMOJI[c2]} <i>beats</i> {EMOJI[c1]}!"

    if winner:
        game["score"][winner] += 1

    game["choices"] = {}

    for user in game["players"]:
        s_self = game["score"][user]
        opp = registry.other_player(game, user)
        s_other = game["score"][opp] if opp is not None else 0
        prefix = "🎉 <i>You took that round!</i>" if winner == user else ("😔 <i>They took that round.</i>" if winner else "🤝")
        text = f"{outcome}\n{prefix}\n\n<b>Score:</b> You {s_self} — Opponent {s_other}"
        await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, parse_mode="HTML")

    if game["score"][u1] >= WINS_NEEDED or game["score"][u2] >= WINS_NEEDED:
        await _end_game(context, session_id)
    else:
        game["round"] += 1
        await send_round(context, session_id)


async def _end_game(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    u1, u2 = game["players"]
    winner = u1 if game["score"][u1] > game["score"][u2] else u2
    loser = u2 if winner == u1 else u1

    init.user_details[winner]["points"] += 8
    init.dirty_users.update([winner, loser])

    await safe_tele_func_call(context.bot.send_message, chat_id=winner, text=WON_MATCH_TEXT, parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=loser, text=LOST_MATCH_TEXT, parse_mode="HTML")

    _teardown(game, session_id)


async def force_end_game(context: ContextTypes.DEFAULT_TYPE, user_id):
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
        init.user_details[other]["points"] += 5
        init.dirty_users.add(other)
    _teardown(game, session_id)


def remove_timeout_job(g):
    job = g.get("timeout_job")
    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass
    g["timeout_job"] = None


def _teardown(game, session_id):
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
