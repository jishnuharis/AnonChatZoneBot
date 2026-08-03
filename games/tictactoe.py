from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from message import PARTNER_LEFT_GAME_TEXT, GAME_ENDED_INACTIVITY_TEXT, DRAW_NOTE_TEXT, GAME_OVER_NOTE_TEXT

import uuid

import init

games = {}
user_to_session = {}

TIMEOUT = 300
GAME_TYPE = "tictactoe"

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


def create_session(user1, user2):
    session_id = str(uuid.uuid4())
    games[session_id] = {
        "players": [user1, user2],
        "symbols": {user1: "❌", user2: "⭕"},
        "board": [""] * 9,
        "turn": user1,
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


def _board_markup(game, session_id, interactive: bool):
    rows = []
    for r in range(3):
        row = []
        for c in range(3):
            i = r * 3 + c
            label = game["board"][i] or "▫️"
            cb = f"ttt|{i}" if interactive else "ttt|noop"
            row.append(InlineKeyboardButton(label, callback_data=cb))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


async def send_board(context: ContextTypes.DEFAULT_TYPE, session_id, extra_note=""):
    game = games.get(session_id)
    if not game:
        return
    remove_timeout_job(game)
    job = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})
    game["timeout_job"] = job

    for user in game["players"]:
        is_turn = (user == game["turn"])
        symbol = game["symbols"][user]
        status = f"<i>Your move! You're</i> {symbol}" if is_turn else f"<i>Waiting on your opponent...</i> (<i>you're</i> {symbol})"
        text = f"⭕❌ <b>Tic Tac Toe</b>\n{status}{extra_note}"
        markup = _board_markup(game, session_id, interactive=is_turn)
        existing_msg_id = game["messages"].get(user)
        if existing_msg_id:
            await safe_tele_func_call(context.bot.edit_message_text, chat_id=user, message_id=existing_msg_id, text=text, reply_markup=markup, parse_mode="HTML")
        else:
            msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, reply_markup=markup, parse_mode="HTML")
            if msg:
                game["messages"][user] = msg.message_id

send_round = send_board


def _check_winner(board):
    for a, b, c in WIN_LINES:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "draw"
    return None


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

    cell = int(data)
    if game["board"][cell]:
        return

    game["board"][cell] = game["symbols"][user_id]
    result = _check_winner(game["board"])

    if result is None:
        game["turn"] = registry.other_player(game, user_id)
        await send_board(context, session_id)
        return

    if result == "draw":
        for user in game["players"]:
            init.user_details[user]["points"] += 3
        init.dirty_users.update(game["players"])
        note = DRAW_NOTE_TEXT
    else:
        winner = user_id
        init.user_details[winner]["points"] += 8
        init.dirty_users.add(winner)
        note = GAME_OVER_NOTE_TEXT

    for user in game["players"]:
        symbol = game["symbols"][user]
        markup = _board_markup(game, session_id, interactive=False)
        if result == "draw":
            text = f"⭕❌ <b>Tic Tac Toe</b>\n<i>You're</i> {symbol}{note}"
        elif user == user_id:
            text = f"⭕❌ <b>Tic Tac Toe</b>\n<i>You're</i> {symbol}{note}\n🎉 <i>You won! +8 points.</i>"
        else:
            text = f"⭕❌ <b>Tic Tac Toe</b>\n<i>You're</i> {symbol}{note}\n😔 <i>You lost this one.</i>"
        msg_id = game["messages"].get(user)
        if msg_id:
            await safe_tele_func_call(context.bot.edit_message_text, chat_id=user, message_id=msg_id, text=text, reply_markup=markup, parse_mode="HTML")

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
