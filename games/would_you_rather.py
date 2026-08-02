import random
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
from message import PARTNER_LEFT_GAME_TEXT, GAME_ENDED_INACTIVITY_TEXT

import init

games = {}
user_to_session = {}

TIMEOUT = 180
GAME_TYPE = "wyr"
TOTAL_ROUNDS = 5

# Prompts grouped by preference tag so we can pull ones that fit the pair when possible,
# plus a generic bucket that always works.
PROMPTS = {
    "Gaming": [
        ("Only ever play mobile games", "Only ever play console games"),
        ("Never play multiplayer again", "Never play singleplayer again"),
    ],
    "Anime": [
        ("Only watch subbed anime forever", "Only watch dubbed anime forever"),
        ("Live in a shonen world", "Live in a slice-of-life world"),
    ],
    "Music": [
        ("Only listen to one artist forever", "Never listen to your favorite genre again"),
        ("Go to a concert every week", "Never go to a concert again"),
    ],
    "Movies": [
        ("Only watch sequels forever", "Only watch original movies forever"),
        ("Watch every movie 30 mins shorter", "Watch every movie 30 mins longer"),
    ],
    "Sports": [
        ("Only ever watch sports, never play", "Only ever play sports, never watch"),
    ],
    "Memes": [
        ("Speak only in memes for a day", "Never send a meme again"),
    ],
    "Relationships": [
        ("Always know when someone's lying to you", "Always be able to hide your own feelings perfectly"),
    ],
    "Study": [
        ("Never take a test again", "Never get a summer break again"),
    ],
    "Politics": [
        ("Have to debate politics every day", "Never be allowed to discuss politics again"),
    ],
    "Flirting": [
        ("Only be able to flirt in text, never voice", "Only be able to flirt in voice, never text"),
    ],
}

GENERIC_PROMPTS = [
    ("Be able to fly", "Be able to turn invisible"),
    ("Always be 10 minutes late", "Always be 20 minutes early"),
    ("Have unlimited money but no free time", "Have unlimited free time but no money"),
    ("Live without music", "Live without movies"),
    ("Know how you'll die", "Know when you'll die"),
    ("Always say what's on your mind", "Never speak again unless spoken to"),
    ("Relive your best day forever", "Never remember your best day at all"),
]


def _prompt_pool(u1, u2):
    p1 = init.user_details.get(u1, {}).get("preferences", 0)
    p2 = init.user_details.get(u2, {}).get("preferences", 0)
    shared_tags = [label for i, (label, _) in enumerate(init.PREFERENCE_TAGS) if (p1 & p2) & (1 << i)]
    pool = list(GENERIC_PROMPTS)
    for tag in shared_tags:
        pool.extend(PROMPTS.get(tag, []))
    return pool


def create_session(user1, user2):
    session_id = str(uuid.uuid4())
    pool = _prompt_pool(user1, user2)
    random.shuffle(pool)
    games[session_id] = {
        "players": [user1, user2],
        "prompts": pool[:TOTAL_ROUNDS] if len(pool) >= TOTAL_ROUNDS else (pool * 2)[:TOTAL_ROUNDS],
        "round": 0,
        "matches": 0,
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


def get_session(user_id):
    return user_to_session.get(user_id)


async def send_round(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    if game["round"] >= len(game["prompts"]):
        await _end_game(context, session_id)
        return

    a, b = game["prompts"][game["round"]]
    game["choices"] = {}
    remove_timeout_job(game)
    game["timeout_job"] = context.job_queue.run_once(timeout_job, when=TIMEOUT, data={"session_id": session_id})

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🅰️ {a}", callback_data="wyr|A")],
        [InlineKeyboardButton(f"🅱️ {b}", callback_data="wyr|B")],
    ])

    for user in game["players"]:
        text = f"🤔 <b>Would You Rather</b> — Round {game['round'] + 1}/{len(game['prompts'])}\n\n<i>Would you rather...</i>\n🅰️ <b>{a}</b>\n<i>or</i>\n🅱️ <b>{b}</b>"
        msg = await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, reply_markup=keyboard, parse_mode="HTML")
        if msg:
            game["messages"][user] = msg.message_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    pick = query.data.split("|")[1]

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
        await safe_tele_func_call(context.bot.edit_message_text, chat_id=user_id, message_id=msg_id, text=f"<i>You picked</i> {'🅰️' if pick == 'A' else '🅱️'}. <i>Waiting on your partner...</i>", parse_mode="HTML")

    game["choices"][user_id] = pick
    other = registry.other_player(game, user_id)
    if other is None:
        return

    if len(game["choices"]) < 2:
        return

    a, b = game["prompts"][game["round"]]
    u1, u2 = game["players"]
    matched = game["choices"][u1] == game["choices"][u2]
    if matched:
        game["matches"] += 1

    for user in game["players"]:
        my_pick = game["choices"][user]
        their_pick = game["choices"][other if user == user_id else user_id]
        summary = f"<i>You picked</i> {'🅰️ ' + a if my_pick == 'A' else '🅱️ ' + b}\n<i>They picked</i> {'🅰️ ' + a if their_pick == 'A' else '🅱️ ' + b}"
        outcome = "💞 <b>You matched!</b>" if matched else "🤷 <b>Different picks this time.</b>"
        await safe_tele_func_call(context.bot.send_message, chat_id=user, text=f"{outcome}\n{summary}", parse_mode="HTML")

    game["round"] += 1
    await send_round(context, session_id)


async def _end_game(context: ContextTypes.DEFAULT_TYPE, session_id):
    game = games.get(session_id)
    if not game:
        return
    total = len(game["prompts"])
    pct = round((game["matches"] / total) * 100) if total else 0
    bonus = game["matches"] * 2

    for user in game["players"]:
        init.user_details[user]["points"] += bonus
    init.dirty_users.update(game["players"])

    text = f"🤔 <b>Would You Rather — Results</b>\n\n<i>You two matched on</i> <b>{game['matches']}/{total}</b> <i>rounds</i> (<b>{pct}%</b> compatibility 💞)\n<i>Both earned +{bonus} points.</i>"
    for user in game["players"]:
        await safe_tele_func_call(context.bot.send_message, chat_id=user, text=text, parse_mode="HTML")

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
