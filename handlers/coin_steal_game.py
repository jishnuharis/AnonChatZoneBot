from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import games.coin_steal
from security import safe_tele_func_call

import init


async def send_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    partner_id = init.user_details.get(user_id).get("partner_id")

    from games.coin_steal import get_session

    if get_session(user_id):
        await update.message.reply_text("You are already in a game. Finish that first.")
        return
    if get_session(partner_id):
        await update.message.reply_text("Your partner is already in a game. Let them finish first.")
        return

    if partner_id in init.game_requests:
        await update.message.reply_text("You can't just spam requests and expect your partner to accept it 💀.")
        return

    if not partner_id:
        await update.message.reply_text("No partner found. Go get one soon to play 💀.")
        return

    if partner_id == user_id:
        await update.message.reply_text("Are you really trying to play with yourself 💀.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data="cs_req|accept"),
            InlineKeyboardButton("❌ Decline", callback_data="cs_req|decline")
        ]
    ]

    await context.bot.send_message(
        chat_id=partner_id,
        text="🎮 Your partner wants to play *Coin Steal*\nDo you accept?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

    await update.message.reply_text("⏳ Waiting for your partner to accept...")
    init.game_requests[partner_id] = user_id


async def handle_cs_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    action = query.data.split("|")[1]

    requester_id = init.game_requests.get(user_id)

    if not requester_id:
        await safe_tele_func_call(query.edit_message_text, text="This request expired or doesn't exist.")
        return

    if action == "decline":
        await safe_tele_func_call(query.edit_message_text, "You declined the request.")
        await context.bot.send_message(chat_id=requester_id, text="Your partner declined the game.")
        init.game_requests.pop(user_id, None)
        return

    elif action == "accept":
        await safe_tele_func_call(query.edit_message_text, text="Request accepted!\nStarting Game...")
        await context.bot.send_message(chat_id=requester_id, text="Your request is accepted! Starting Game...")

        from games.coin_steal import create_session, send_round, timeout_job

        session_id = create_session(requester_id, user_id)
        await send_round(context, session_id)

        game = games.coin_steal.games[session_id]

        job = context.job_queue.run_once(timeout_job, when=180, data={"session_id": session_id})

        game["timeout_job"] = job

        init.game_requests.pop(user_id, None)

