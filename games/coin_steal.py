from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import time
import uuid

import init

games = {}
user_to_session = {}

TIMEOUT = 300


def create_session(user1, user2):
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

    xtra = "\n*x2 Multiplier* has been added for this round" if r == 3 else ""
    txt = f"🎯 Round {r}:\nChoose wisely...{xtra}"

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
        msg = await context.bot.send_message(chat_id=user, text=txt, reply_markup=keyboard, parse_mode="Markdown")
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
        await safe_tele_func_call(context.bot.send_message, chat_id=user_id, text="You already chose. Chill 😭")
        return

    msg_id = game["messages"].get(user_id)
    if msg_id:
        game["messages"].pop(user_id, None)
        await safe_tele_func_call(
            context.bot.edit_message_text,
            chat_id=user_id,
            message_id=msg_id,
            text="Your choice has been locked in 🔒."
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

    if len(game["choices"]) == 1:
        await safe_tele_func_call(context.bot.send_message, chat_id=other_user, text="Your opponent made their move... do you trust them? 👀")
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

    if c1 == "save" and c2 == "save":
        s1, s2 = 1, 1
        m1 = m2 = "You guys really trusted each other! 👀\nGood job saving the other for now 😏"
    elif c1 == "steal" and c2 == "steal":
        s1, s2 = 0, 0
        m1 = m2 = "Both chose greed over the other and stole. Now no one wins 😏."
    elif c1 == "steal" and c2 == "save":
        s1, s2 = 2 * multiplier, 0
        m1 = "You shouldn't have done that to them 💀.\nThey saved you..."
        m2 = "You sure trusted the wrong one this time 💀.\nYou just got stolen..."
    elif c1 == "save" and c2 == "steal":
        s1, s2 = 0, 2 * multiplier
        m1 = "You sure trusted the wrong one this time 💀.\nYou just got stolen..."
        m2 = "You shouldn't have done that to them 💀.\nThey saved you..."

    game["score"][u1] += s1
    game["score"][u2] += s2

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=u1,
        text=f"{m1}\n\nYou: {game['score'][u1]}\nOpponent: {game['score'][u2]}"
    )
    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=u2,
        text=f"{m2}\n\nYou: {game['score'][u2]}\nOpponent: {game['score'][u1]}"
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
    m1, m2 = "", ""

    s1 = game["score"][u1]
    s2 = game["score"][u2]

    m1 += "The game has come to an end. Well played both of you.\n\n"

    if s1 > s2:
        m1 += "You really won by deceiving them 💔."
        m2 += "Maybe that's why they tell us not to trust anyone on the internet 🥀."
        init.user_details[u1]["points"] += 10
        init.dirty_users.add(u1)
    elif s2 > s1:
        m1 += "Maybe that's why they tell us not to trust anyone on the internet 🥀."
        m2 += "You really won by deceiving them 💔."
        init.user_details[u2]["points"] += 10
        init.dirty_users.add(u2)
    else:
        m1 += "You guys managed to make it a draw 👏.\nWell played for sure!"
        m2 += "You guys managed to make it a draw 👏.\nWell played for sure!"

    await safe_tele_func_call(context.bot.send_message, chat_id=u1, text=m1)
    await safe_tele_func_call(context.bot.send_message, chat_id=u2, text=m2)

    remove_timeout_job(game)

    for user in game["players"]:
        user_to_session.pop(user, None)

    games.pop(session_id, None)


async def force_end_game(context: ContextTypes.DEFAULT_TYPE, user_id):
    session_id = get_session(user_id)
    if not session_id:
        return

    game = games.get(session_id)
    if not game:
        return

    u1, u2 = game["players"]

    other = u2 if user_id == u1 else u1

    await safe_tele_func_call(context.bot.send_message, chat_id=other, text="Your partner left the game. Game ended...")
    init.user_details[other]["points"] += 5
    init.dirty_users.add(other)

    remove_timeout_job(game)

    for user in game["players"]:
        user_to_session.pop(user, None)

    games.pop(session_id, None)


def remove_timeout_job(g):
    job = g.get("timeout_job")

    if job:
        try:
            job.schedule_removal()
        except Exception:
            pass
        g["timeout_job"] = None


async def timeout_job(context: ContextTypes.DEFAULT_TYPE):
    session_id = context.job.data["session_id"]

    game = games.get(session_id)
    if not game:
        return

    u1, u2 = game["players"]

    await safe_tele_func_call(context.bot.send_message, chat_id=u1, text="Game ended due to inactivity.\nRestart if you guys wanna play again.")
    await safe_tele_func_call(context.bot.send_message, chat_id=u2, text="Game ended due to inactivity.\nRestart if you guys wanna play again.")
    init.user_details[u1]["points"] += 1
    init.user_details[u2]["points"] += 1

    remove_timeout_job(game)

    for user in game["players"]:
        user_to_session.pop(user, None)

    games.pop(session_id, None)
