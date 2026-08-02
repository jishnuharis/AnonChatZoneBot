from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from message import (
    ALREADY_CHOSE_TEXT, CHOICE_LOCKED_IN_TEXT, OPPONENT_MOVED_TEXT, MUTUAL_SAVE_NO_STREAK_TEXT,
    BOTH_STOLE_TEXT, GOT_STOLEN_FROM_TEXT, TRUSTED_WRONG_ONE_TEXT, COIN_STEAL_END_INTRO_TEXT,
    WON_BY_DECEIVING_TEXT, LOST_TRUST_LESSON_TEXT, COIN_STEAL_DRAW_TEXT, PARTNER_LEFT_GAME_TEXT,
    COIN_STEAL_TIMEOUT_TEXT,
)

import time
import uuid

import init

games = {}
user_to_session = {}

TIMEOUT = 300
GAME_TYPE = "coinsteal"


def create_session(user1, user2):
    session_id = str(uuid.uuid4())

    games[session_id] = {
        "players": [user1, user2],
        "choices": {},
        "score": {user1: 0, user2: 0},
        "round": 1,
        "messages": {},
        "start_time": time.time(),
        "active": True,
        "timeout_job": None,
        "mutual_save_streak": 0,
    }

    user_to_session[user1] = session_id
    user_to_session[user2] = session_id
    registry.register(user1, GAME_TYPE)
    registry.register(user2, GAME_TYPE)

    return session_id


def get_session(user_id):
    return user_to_session.get(user_id)


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    r = game["round"]

    xtra = "\n<b>🔥 Wildcard Round</b> — <i>stakes are doubled this time</i>" if r == 3 else ""
    txt = f"<i>🎯 Round {r}: Choose wisely...</i>{xtra}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Steal 😈", callback_data="cs|steal"),
            InlineKeyboardButton("Save 🤝", callback_data="cs|save")
        ]
    ])

    remove_timeout_job(game)

    job = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})
    game["timeout_job"] = job

    game["start_time"] = time.time()
    game["messages"].clear()
    for user in game["players"]:
        msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=txt, reply_markup=keyboard, parse_mode="HTML")
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
    if not game:
        return

    if user_id not in game["messages"]:
        return

    if user_id in game["choices"]:
        await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=ALREADY_CHOSE_TEXT, parse_mode="HTML")
        return

    msg_id = game["messages"].get(user_id)
    if msg_id:
        game["messages"].pop(user_id, None)
        await safe_tele_func_call(
            context.bot.edit_message_text,
            chat_id=user_id,
            message_id=msg_id,
            text=CHOICE_LOCKED_IN_TEXT,
            parse_mode="HTML"
        )

    await handle_choice(context, user_id, choice)


async def handle_choice(context: ContextTypes.DEFAULT_TYPE, user_id, choice):
    session_id = get_session(user_id)
    if not session_id:
        return

    game = games.get(session_id)
    if not game:
        return

    game["choices"][user_id] = choice

    choice_text = "Steal 😈" if choice == "steal" else "Save 🤝"
    other_user = registry.other_player(game, user_id)
    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=f"<i>You chose to</i> <b>{choice_text}</b>.", parse_mode="HTML")

    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})
    game["start_time"] = time.time()

    if len(game["choices"]) == 1 and other_user is not None:
        await safe_tele_func_call(context.bot.send_message, chat_id=other_user, text=OPPONENT_MOVED_TEXT, parse_mode="HTML")
    if len(game["choices"]) == 2:
        await resolve_round(context, session_id)


async def resolve_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    u1, u2 = game["players"]
    m1, m2 = "", ""

    c1 = game["choices"][u1]
    c2 = game["choices"][u2]
    r = game["round"]

    multiplier = 1
    if r == 3 and ((c1 == "steal" and c2 == "save") or (c1 == "save" and c2 == "steal")):
        multiplier = 2

    streak_bonus = 0
    if c1 == "save" and c2 == "save":
        s1, s2 = 1, 1
        game["mutual_save_streak"] += 1
        streak = game["mutual_save_streak"]
        if streak >= 2:
            streak_bonus = 1
            s1 += streak_bonus
            s2 += streak_bonus
            m1 = m2 = f"<i>You guys really trusted each other! 👀\n🔥 Trust streak x{streak}! Bonus coin earned.</i>"
        else:
            m1 = m2 = MUTUAL_SAVE_NO_STREAK_TEXT
    elif c1 == "steal" and c2 == "steal":
        s1, s2 = 0, 0
        game["mutual_save_streak"] = 0
        m1 = m2 = BOTH_STOLE_TEXT
    elif c1 == "steal" and c2 == "save":
        s1, s2 = 2 * multiplier, 0
        game["mutual_save_streak"] = 0
        m1 = GOT_STOLEN_FROM_TEXT
        m2 = TRUSTED_WRONG_ONE_TEXT
    elif c1 == "save" and c2 == "steal":
        s1, s2 = 0, 2 * multiplier
        game["mutual_save_streak"] = 0
        m1 = TRUSTED_WRONG_ONE_TEXT
        m2 = GOT_STOLEN_FROM_TEXT

    game["score"][u1] += s1
    game["score"][u2] += s2

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=u1,
        text=f"{m1}\n\n<b>You:</b> {game['score'][u1]}\n<b>Opponent:</b> {game['score'][u2]}",
        parse_mode="HTML"
    )
    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=u2,
        text=f"{m2}\n\n<b>You:</b> {game['score'][u2]}\n<b>Opponent:</b> {game['score'][u1]}",
        parse_mode="HTML"
    )

    game["choices"] = {}

    if game["round"] == 3:
        await end_game(context, session_id)
    else:
        game["round"] += 1
        await send_round(context, session_id)


async def end_game(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    u1, u2 = game["players"]

    s1 = game["score"][u1]
    s2 = game["score"][u2]

    intro = COIN_STEAL_END_INTRO_TEXT

    if s1 > s2:
        m1 = intro + WON_BY_DECEIVING_TEXT
        m2 = intro + LOST_TRUST_LESSON_TEXT
        init.user_details[u1]["points"] += 10
        init.dirty_users.add(u1)
    elif s2 > s1:
        m1 = intro + LOST_TRUST_LESSON_TEXT
        m2 = intro + WON_BY_DECEIVING_TEXT
        init.user_details[u2]["points"] += 10
        init.dirty_users.add(u2)
    else:
        draw_line = COIN_STEAL_DRAW_TEXT
        m1 = intro + draw_line
        m2 = intro + draw_line

    await safe_tele_func_call(context.bot.send_message, chat_id=u1, text=m1, parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=u2, text=m2, parse_mode="HTML")

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

    u1, u2 = game["players"]

    other = u2 if user_id == u1 else u1

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

    u1, u2 = game["players"]

    await safe_tele_func_call(context.bot.send_message, chat_id=u1, text=COIN_STEAL_TIMEOUT_TEXT, parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=u2, text=COIN_STEAL_TIMEOUT_TEXT, parse_mode="HTML")
    init.user_details[u1]["points"] += 1
    init.user_details[u2]["points"] += 1
    init.dirty_users.update([u1, u2])

    _teardown(game, session_id)
