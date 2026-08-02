from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from games import registry
import games.coin_steal as coin_steal
import games.tictactoe as tictactoe
import games.rps as rps
import games.guess_it as guess_it
import games.would_you_rather as would_you_rather

from message import (
    NO_PARTNER_FOR_GAME_TEXT, CANT_PLAY_WITH_YOURSELF_TEXT, ALREADY_IN_GAME_TEXT,
    PARTNER_ALREADY_IN_GAME_TEXT, CANT_SPAM_GAME_REQUESTS_TEXT, WAITING_FOR_PARTNER_ACCEPT_TEXT,
    GAME_REQUEST_EXPIRED_TEXT, YOU_DECLINED_REQUEST_TEXT, PARTNER_DECLINED_REQUEST_TEXT,
)

import init

# game_type -> (label, module)
GAME_MODULES = {
    "coinsteal": ("Coin Steal 🪙", coin_steal),
    "tictactoe": ("Tic Tac Toe ⭕❌", tictactoe),
    "rps": ("Rock Paper Scissors 🪨📄✂️", rps),
    "guessit": ("Guess It 🔢", guess_it),
    "wyr": ("Would You Rather 🤔", would_you_rather),
}

# Wire up force-end handlers with the registry once, on import
for _game_type, (_label, _module) in GAME_MODULES.items():
    registry.set_force_end_handler(_game_type, _module.force_end_game)


def clear_pending_requests(user_id: int):
    """Removes any game request that involves user_id, whether they're the
    target (waiting on them to accept/decline) or the requester (waiting on
    someone else). Call this whenever a chat ends (/stop, /next) or a game
    request is manually cancelled (/cancel) - otherwise a stale request can
    sit around and later be accepted against a partner who's since moved on,
    which corrupts game state (mismatched sessions/registry entries) and is
    the root cause behind the "coroutine raised StopIteration" crashes."""
    init.game_requests.pop(user_id, None)
    for target_id, req in list(init.game_requests.items()):
        if req["from"] == user_id:
            init.game_requests.pop(target_id, None)


async def send_request(update: Update, context: ContextTypes.DEFAULT_TYPE, game_type: str):
    user_id = update.effective_user.id
    partner_id = init.user_details.get(user_id, {}).get("partner_id")

    label, module = GAME_MODULES[game_type]

    if not partner_id:
        await safe_tele_func_call(update.effective_message.reply_text, text=NO_PARTNER_FOR_GAME_TEXT, parse_mode="HTML")
        return

    if registry.get_active(user_id):
        await safe_tele_func_call(update.effective_message.reply_text, text=ALREADY_IN_GAME_TEXT, parse_mode="HTML")
        return

    if registry.get_active(partner_id):
        await safe_tele_func_call(update.effective_message.reply_text, text=PARTNER_ALREADY_IN_GAME_TEXT, parse_mode="HTML")
        return

    if partner_id in init.game_requests:
        await safe_tele_func_call(update.effective_message.reply_text, text=CANT_SPAM_GAME_REQUESTS_TEXT, parse_mode="HTML")
        return

    keyboard = [[
        InlineKeyboardButton("✅ Accept", callback_data="gamereq|accept"),
        InlineKeyboardButton("❌ Decline", callback_data="gamereq|decline"),
    ]]

    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=partner_id,
        text=f"🎮 <i>Your partner wants to play</i> <b>{label}</b>\n<i>Do you accept?</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML",
    )

    await safe_tele_func_call(update.effective_message.reply_text, text=WAITING_FOR_PARTNER_ACCEPT_TEXT, parse_mode="HTML")
    init.game_requests[partner_id] = {"from": user_id, "game": game_type}


async def handle_game_request_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data.split("|")[1]

    request = init.game_requests.get(user_id)
    if not request:
        await safe_tele_func_call(query.edit_message_text, text=GAME_REQUEST_EXPIRED_TEXT, parse_mode="HTML")
        return

    requester_id = request["from"]
    game_type = request["game"]
    label, module = GAME_MODULES[game_type]

    if action == "decline":
        await safe_tele_func_call(query.edit_message_text, text=YOU_DECLINED_REQUEST_TEXT, parse_mode="HTML")
        await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=PARTNER_DECLINED_REQUEST_TEXT, parse_mode="HTML")
        init.game_requests.pop(user_id, None)
        return

    # accept - but first make sure this request is still valid. It can go stale if either side
    # left the chat (/stop, /next) or started/joined another game while it was pending; blindly
    # creating a session in that case corrupts both players' game state (mismatched sessions and
    # registry entries) and is what used to cause "coroutine raised StopIteration" crashes.
    still_partnered = init.user_details.get(requester_id, {}).get("partner_id") == user_id
    either_already_in_game = registry.get_active(requester_id) or registry.get_active(user_id)

    if not still_partnered or either_already_in_game:
        init.game_requests.pop(user_id, None)
        await safe_tele_func_call(query.edit_message_text, text=GAME_REQUEST_EXPIRED_TEXT, parse_mode="HTML")
        await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=GAME_REQUEST_EXPIRED_TEXT, parse_mode="HTML")
        return

    await safe_tele_func_call(query.edit_message_text, text=f"<b>Request accepted!\nStarting {label}...</b>", parse_mode="HTML")
    await safe_tele_func_call(context.bot.send_message, chat_id=requester_id, text=f"<b>Your request has been accepted!\nStarting {label}...</b>", parse_mode="HTML")

    session_id = module.create_session(requester_id, user_id)
    await module.send_round(context, session_id)

    init.game_requests.pop(user_id, None)
