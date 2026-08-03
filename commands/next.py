from telegram import Update
from telegram.ext import ContextTypes

from commands.find import find

from handlers.setup import check_user_profile
from handlers.rating import ask_for_rating
from security import safe_tele_func_call
from games.registry import end_any_active_game
from games.game_requests import clear_pending_requests
from message import PARTNER_LEFT_CHAT_TEXT, PARTNER_SKIPPED_TEXT, NOT_IN_CHAT_USE_FIND_TEXT

import init


@check_user_profile
async def skip_partner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id in init.active_pairs:
        partner = init.active_pairs.pop(user_id)
        init.user_details[partner]["partner_id"] = None
        init.user_details[user_id]["partner_id"] = None
        init.active_pairs.pop(partner, None)
        init.message_map.pop(user_id, None)
        init.message_map.pop(partner, None)

        init.dirty_users.update([user_id, partner])

        await end_any_active_game(context, user_id)
        await end_any_active_game(context, partner)

        clear_pending_requests(user_id)
        clear_pending_requests(partner)

        await safe_tele_func_call(context.bot.send_message, chat_id=partner, text=PARTNER_LEFT_CHAT_TEXT, parse_mode="HTML")
        await safe_tele_func_call(update.message.reply_text, text=PARTNER_SKIPPED_TEXT, parse_mode="HTML")

        await ask_for_rating(context.bot, user_id, partner)
        await ask_for_rating(context.bot, partner, user_id)

        await find(update, context)
    else:
        await safe_tele_func_call(update.message.reply_text, text=NOT_IN_CHAT_USE_FIND_TEXT, parse_mode="HTML")
