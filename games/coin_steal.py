from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import time
import uuid
import random
import asyncio

import init

games = {}
user_to_session = {}

TIMEOUT = 300

# 🔥 DEBUG MODE
DEBUG_MODE = False
DEBUG_BOT_ID = -999999


def create_session(user1, user2=None):
    if user1 == int(init.OWNER):
        DEBUG_MODE = True
    if DEBUG_MODE:
        user2 = DEBUG_BOT_ID

    session_id = str(uuid.uuid4())

    games[session_id] = {
        "players": [user1, user2],
        "choices": {},
        "score": {user1: 0, user2: 0},
        "round": 1,
        "messages": {},
        "start_time": time.time(),
        "timeout_job": None,
    }

    user_to_session[user1] = session_id
    user_to_session[user2] = session_id

    return session_id


def get_session(user_id):
    return user_to_session.get(user_id)


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return

    r = game["round"]

    xtra = "\n*x2 Multiplier*" if r == 3 else ""
    txt = f"🎯 Round {r}:{xtra}\nChoose wisely..."

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
        if user == DEBUG_BOT_ID:
            continue

        msg = await context.bot.send_message(
            chat_id=user,
            text=txt,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
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

    if user_id in game["choices"]:
        await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text="You already chose. Chill 😭")
        return

    msg_id = game["messages"].pop(user_id, None)
    if msg_id:
        await safe_tele_func_call(
            context.bot.edit_message_text,
            chat_id=user_id,
            message_id=msg_id,
            text="Choice locked in 🔒"
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
    other_user = next(u for u in game["players"] if u != user_id)

    await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text=f"You chose to {choice_text}.")

    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})
    game["start_time"] = time.time()

    # 🔥 DEBUG BOT MOVE
    if DEBUG_MODE and other_user == DEBUG_BOT_ID:
        await simulate_bot_choice(context, session_id)

    elif len(game["choices"]) == 1:
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=other_user,
            text="Your opponent made their move... do you trust them? 👀"
        )

    if len(game["choices"]) == 2:
        await resolve_round(context, session_id)


async def simulate_bot_choice(context, session_id):
    await asyncio.sleep(1.5)

    game = games.get(session_id)
    if not game:
        return

    bot_choice = random.choice(["steal", "save"])
    game["choices"][DEBUG_BOT_ID] = bot_choice

    real_user = next(u for u in game["players"] if u != DEBUG_BOT_ID)

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=real_user,
        text="Opponent has made their move... 😶"
    )

    if len(game["choices"]) == 2:
        await resolve_round(context, session_id)


async def resolve_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return

    u1, u2 = game["players"]

    c1 = game["choices"][u1]
    c2 = game["choices"][u2]
    r = game["round"]

    multiplier = 1
    if r == 3 and ((c1 != c2)):
        multiplier = 2

    if c1 == "save" and c2 == "save":
        s1, s2 = 1, 1
        m1 = m2 = "You both trusted each other 👀"
    elif c1 == "steal" and c2 == "steal":
        s1, s2 = 0, 0
        m1 = m2 = "Both went greedy 😏"
    elif c1 == "steal":
        s1, s2 = 2 * multiplier, 0
        m1, m2 = "You betrayed them 💀", "You got betrayed 💀"
    else:
        s1, s2 = 0, 2 * multiplier
        m1, m2 = "You got betrayed 💀", "You betrayed them 💀"

    game["score"][u1] += s1
    game["score"][u2] += s2

    for user, msg, opp in [
        (u1, m1, u2),
        (u2, m2, u1)
    ]:
        if user == DEBUG_BOT_ID:
            continue

        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user,
            text=f"{msg}\n\nYou: {game['score'][user]}\nOpponent: {game['score'][opp]}"
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

    real_user = u1 if u1 != DEBUG_BOT_ID else u2

    if s1 > s2:
        msg = "You won 😈"
    elif s2 > s1:
        msg = "You lost 😭"
    else:
        msg = "Draw 🤝"

    await safe_tele_func_call(context.bot.send_message, chat_id=real_user, text=msg)

    remove_timeout_job(game)

    for user in game["players"]:
        user_to_session.pop(user, None)

    games.pop(session_id, None)


def remove_timeout_job(g):
    job = g.get("timeout_job")
    if job:
        try:
            job.schedule_removal()
        except:
            pass
        g["timeout_job"] = None


async def timeout_job(context: ContextTypes.DEFAULT_TYPE):
    session_id = context.job.data["session_id"]

    game = games.get(session_id)
    if not game:
        return

    for user in game["players"]:
        if user == DEBUG_BOT_ID:
            continue

        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=user,
            text="Game ended due to inactivity."
        )

    remove_timeout_job(game)

    for user in game["players"]:
        user_to_session.pop(user, None)

    games.pop(session_id, None)