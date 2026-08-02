import random
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from message import PARTNER_LEFT_GAME_TEXT, GAME_ENDED_INACTIVITY_TEXT, WON_MATCH_TEXT, LOST_MATCH_TEXT

import init

games = {}
user_to_session = {}

TIMEOUT = 180
GAME_TYPE = "guessit"
RANGE_MAX = 20
ROUNDS_TO_WIN = 2  # best of 3


def create_session(user1, user2):
    session_id = str(uuid.uuid4())
    games[session_id] = {
        "players": [user1, user2],
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


def _new_round(game):
    game["secret"] = random.randint(1, RANGE_MAX)
    game["guessed"] = set()
    game["turn"] = game["players"][0] if game["round"] % 2 == 1 else game["players"][1]
    game["last_distance"] = {}


def _keyboard(game, interactive: bool):
    rows, row = [], []
    for n in range(1, RANGE_MAX + 1):
        label = "✖️" if n in game["guessed"] else str(n)
        cb = f"gi|{n}" if (interactive and n not in game["guessed"]) else "gi|noop"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id, note=""):
    game = games.get(session_id)
    if not game:
        return
    if "secret" not in game:
        _new_round(game)

    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})

    for user in game["players"]:
        is_turn = (user == game["turn"])
        status = "<i>Your turn — pick a number!</i>" if is_turn else "<i>Waiting for your opponent's guess...</i>"
        text = f"🔢 <b>Guess It</b> — Round {game['round']}\n<i>Secret number is between 1 and {RANGE_MAX}.</i>\n{status}{note}"
        markup = _keyboard(game, interactive=is_turn)
        msg_id = game["messages"].get(user)
        if msg_id:
            await safe_tele_func_call(context.bot.edit_message_text, chat_id=user, message_id=msg_id, text=text, reply_markup=markup, parse_mode="HTML")
        else:
            msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, reply_markup=markup, parse_mode="HTML")
            if msg:
                game["messages"][user] = msg.message_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data.split("|")[1]

    session_id = get_session(user_id)
    if not session_id:
        return
    game = games.get(session_id)
    if not game or not game["active"]:
        return
    if data == "noop" or game["turn"] != user_id:
        return

    guess = int(data)
    game["guessed"].add(guess)
    other = registry.other_player(game, user_id)
    if other is None:
        return

    if guess == game["secret"]:
        game["score"][user_id] += 1
        for user in game["players"]:
            tag = "🎉 <i>You guessed it!</i>" if user == user_id else "😔 <i>Your opponent got it.</i>"
            note = f"\n\n🎯 <b>{guess} was it!</b> " + ("You win this round." if user == user_id else "They win this round.")
            opp_score = game["score"][registry.other_player(game, user)]
            text = f"🔢 <b>Guess It</b>\n{tag}\n<i>The number was</i> <b>{game['secret']}</b>.{note}\n\n<b>Score:</b> You {game['score'][user]} — Opponent {opp_score}"
            await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, parse_mode="HTML")

        if game["score"][user_id] >= ROUNDS_TO_WIN or game["score"][other] >= ROUNDS_TO_WIN:
            await _end_game(context, session_id)
        else:
            game["round"] += 1
            game.pop("secret", None)
            await send_round(context, session_id)
        return

    hint = "🔥 Higher" if guess < game["secret"] else "❄️ Lower"
    game["turn"] = other
    await send_round(context, session_id, note=f"\n\n<i>Last guess</i> {guess} <i>was too {'low' if guess < game['secret'] else 'high'}.</i> {hint}!")


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
