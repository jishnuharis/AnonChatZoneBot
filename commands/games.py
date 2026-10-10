import time
import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile
from security import safe_tele_func_call
from games.game_requests import GAME_MODULES
from games import registry
from message import NEED_PARTNER_FOR_GAME_TEXT, PICK_GAME_TEXT, SENDING_GAME_REQUEST_TEXT
from group_helper import is_group_chat, is_group_admin, get_group_redirect_keyboard

import init


@check_user_profile
async def games_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Opens the game menu in 1-on-1 DM or initiates an open game challenge in a group.
    """
    user_id = update.effective_user.id

    if is_group_chat(update):
        # 1. Presence check
        if user_id not in init.user_details:
            await init.ensure_user_loaded(user_id)
        user_data = init.user_details.get(user_id)
        if not user_data or not all([user_data.get("gender"), user_data.get("age"), user_data.get("country")]):
            bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
            await safe_tele_func_call(
                update.message.reply_text,
                text="⚠️ <b>You haven't registered with the bot yet!</b>\n\nStart the bot first in private chat to play games.",
                reply_markup=get_group_redirect_keyboard(bot_username, "start"),
                parse_mode="HTML"
            )
            return

        # 2. Check if already in active game
        if registry.get_active(user_id):
            await safe_tele_func_call(
                update.message.reply_text,
                text="⚠️ <b>You already have an active game running!</b>\nFinish your current game before starting another.",
                parse_mode="HTML"
            )
            return

        # 3. Present group game menu
        caller_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
        keyboard = [
            [InlineKeyboardButton(label, callback_data=f"grpgame|{game_type}|{user_id}")]
            for game_type, (label, _module) in GAME_MODULES.items()
        ]
        await safe_tele_func_call(
            update.message.reply_text,
            text=f"🎮 <b>{caller_tag} wants to launch a game challenge!</b>\n\n<i>Choose a mini-game below to challenge the group:</i>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return

    # DM behavior
    if not init.user_details.get(user_id, {}).get("partner_id"):
        await safe_tele_func_call(update.message.reply_text, text=NEED_PARTNER_FOR_GAME_TEXT, parse_mode="HTML")
        return

    keyboard = [[InlineKeyboardButton(label, callback_data=f"gamemenu|{game_type}")] for game_type, (label, _module) in GAME_MODULES.items()]
    await safe_tele_func_call(update.message.reply_text, text=PICK_GAME_TEXT, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")


async def handle_games_menu_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles 1-on-1 DM game menu selection."""
    from games.game_requests import send_request

    query = update.callback_query
    await query.answer()
    game_type = query.data.split("|")[1]
    await safe_tele_func_call(query.edit_message_text, text=SENDING_GAME_REQUEST_TEXT, parse_mode="HTML")
    await send_request(update, context, game_type)


async def handle_group_game_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles challenger selecting a game from the group game menu."""
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split("|")
    game_type = parts[1]
    challenger_id = int(parts[2])
    user_id = update.effective_user.id

    if user_id != challenger_id:
        await query.answer("⚠️ Only the challenger can pick the game!", show_alert=True)
        return

    await query.answer()

    label, _module = GAME_MODULES.get(game_type, ("Mini-Game", None))
    chal_id = str(uuid.uuid4())[:8]
    caller_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name

    init.group_games[chal_id] = {
        "challenger_id": user_id,
        "challenger_tag": caller_tag,
        "game_type": game_type,
        "chat_id": update.effective_chat.id,
        "message_id": query.message.message_id,
        "status": "waiting",
        "created_at": time.time(),
    }

    challenge_text = (
        f"🎮 <b>Open Challenge: {label}!</b>\n\n"
        f"<b>Challenger:</b> {caller_tag}\n\n"
        f"<i>First member to accept will duel {caller_tag} in private DMs!</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ Accept Challenge", callback_data=f"grp_acc|{chal_id}")],
        [InlineKeyboardButton("❌ Cancel Challenge", callback_data=f"grp_can|{chal_id}")],
    ])
    await safe_tele_func_call(
        query.edit_message_text,
        text=challenge_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )


async def handle_group_challenge_accept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles a member accepting an open group game challenge."""
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split("|")
    chal_id = parts[1] if len(parts) > 1 else ""

    chal = init.group_games.get(chal_id)
    if not chal or chal.get("status") != "waiting":
        await query.answer("⏳ This challenge is no longer available or has already been accepted.", show_alert=True)
        return

    clicker_id = update.effective_user.id
    challenger_id = chal["challenger_id"]

    if clicker_id == challenger_id:
        await query.answer("😅 You cannot accept your own challenge!", show_alert=True)
        return

    # Check active games
    if registry.get_active(clicker_id):
        await query.answer("⚠️ You already have an active game running! Finish it first.", show_alert=True)
        return

    if registry.get_active(challenger_id):
        await query.answer("⚠️ The challenger is currently in another game! Try again shortly.", show_alert=True)
        return

    # Ensure opponent is registered in bot
    if clicker_id not in init.user_details:
        await init.ensure_user_loaded(clicker_id)
    opp_data = init.user_details.get(clicker_id)
    bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
    if not opp_data or not all([opp_data.get("gender"), opp_data.get("age"), opp_data.get("country")]):
        await query.answer("⚠️ Please start the bot in private DM first before accepting!", show_alert=True)
        return

    await query.answer()

    chal["status"] = "playing"
    chal["opponent_id"] = clicker_id
    opponent_tag = f"@{update.effective_user.username}" if update.effective_user.username else update.effective_user.first_name
    chal["opponent_tag"] = opponent_tag

    game_type = chal["game_type"]
    label, module = GAME_MODULES[game_type]

    # Update group message
    accepted_text = (
        f"⚔️ <b>Duel Accepted!</b>\n\n"
        f"<b>{chal['challenger_tag']}</b> 🆚 <b>{opponent_tag}</b>\n"
        f"<b>Game:</b> {label}\n\n"
        f"👉 <i>Head over to your private DMs with the bot to make your moves!</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 Play Game Now", url=f"https://t.me/{bot_username}")]
    ])
    await safe_tele_func_call(
        query.edit_message_text,
        text=accepted_text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    # Launch game session in private DM
    session_id = module.create_session(challenger_id, clicker_id)

    # Save session reference to group games
    init.group_games[session_id] = {
        "chat_id": chal["chat_id"],
        "challenger_id": challenger_id,
        "opponent_id": clicker_id,
        "challenger_tag": chal["challenger_tag"],
        "opponent_tag": opponent_tag,
        "game_label": label,
    }

    # Notify challenger in DM
    await safe_tele_func_call(
        context.bot.send_message,
        chat_id=challenger_id,
        text=f"⚔️ <b>{opponent_tag} accepted your challenge in {label}!</b>\n\nStarting round below:",
        parse_mode="HTML"
    )

    # Start the game round
    await module.send_round(context, session_id)


async def handle_group_challenge_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles challenger or group admin cancelling a waiting group challenge."""
    query = update.callback_query
    if not query or not query.data:
        return

    parts = query.data.split("|")
    chal_id = parts[1] if len(parts) > 1 else ""

    chal = init.group_games.get(chal_id)
    if not chal:
        await query.answer("Challenge expired or not found.", show_alert=True)
        return

    user_id = update.effective_user.id
    is_admin_user = await is_group_admin(context, update.effective_chat.id, user_id)

    if user_id != chal["challenger_id"] and not is_admin_user:
        await query.answer("⚠️ Only the challenger or a group admin can cancel this challenge!", show_alert=True)
        return

    init.group_games.pop(chal_id, None)
    await query.answer("Challenge cancelled.")
    await safe_tele_func_call(
        query.edit_message_text,
        text=f"🛑 <i>Challenge in {GAME_MODULES.get(chal.get('game_type'), ('Game', None))[0]} was cancelled.</i>",
        parse_mode="HTML"
    )
