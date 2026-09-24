from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from moderation import REPORT_REASONS, file_report
from saveNload import record_user_rating, add_user_block
from message import RATE_PROMPT_TEXT, REPORT_REASON_PROMPT_TEXT, REPORT_LOGGED_TEXT, FEEDBACK_THANKS_TEXT

import init
import referral


def _feedback_keyboard(to_id: int, voted: bool, reported: bool, blocked: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    vote_row = []
    if not voted:
        vote_row.extend([
            InlineKeyboardButton("👍", callback_data=f"rate|{to_id}|up"),
            InlineKeyboardButton("👎", callback_data=f"rate|{to_id}|down")
        ])
    if vote_row:
        buttons.append(vote_row)

    action_row = []
    if not reported:
        action_row.append(InlineKeyboardButton("🚩 Report", callback_data=f"report|{to_id}"))
    if not blocked:
        action_row.append(InlineKeyboardButton("🚫 Block", callback_data=f"rateblock|{to_id}"))
    if action_row:
        buttons.append(action_row)

    return InlineKeyboardMarkup(buttons)


async def ask_for_rating(bot, from_id: int, to_id: int):
    markup = _feedback_keyboard(to_id, voted=False, reported=False, blocked=False)
    user_track = init.user_details.setdefault(to_id, {}).setdefault("feedback_track", {})
    user_track[from_id] = {"voted": False, "reported": False, "blocked": False}

    await safe_tele_func_call(
        bot.send_message,
        chat_id=from_id,
        text=RATE_PROMPT_TEXT,
        reply_markup=markup,
        parse_mode="HTML"
    )

    await referral.maybe_announce(bot, from_id)


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query: CallbackQuery = update.callback_query
    await query.answer()
    data = query.data.split("|")
    if not (2 <= len(data) <= 3):
        return

    action = data[0]
    target_id = int(data[1])

    track = init.user_details.setdefault(target_id, {}).setdefault("feedback_track", {})
    track.setdefault(user_id, {"voted": False, "reported": False, "blocked": False})

    if action == "rate":
        vote_type = data[2]
        if not track[user_id]["voted"]:
            await record_user_rating(user_id, target_id, vote_type)
            votes = init.user_details[target_id].setdefault("votes", {"up": 0, "down": 0})
            votes[vote_type] = votes.get(vote_type, 0) + 1
            track[user_id]["voted"] = True
            init.dirty_users.add(target_id)

        await _refresh_feedback_message(query, target_id, track[user_id])
        return

    if action == "rateblock":
        if not track[user_id]["blocked"]:
            await add_user_block(user_id, target_id)
            track[user_id]["blocked"] = True
            await safe_tele_func_call(query.answer, "🚫 User blocked! You will not match with them for the next 24 hours.", show_alert=True)
        await _refresh_feedback_message(query, target_id, track[user_id])
        return

    if action == "report":
        if track[user_id]["reported"]:
            return
        buttons = [[InlineKeyboardButton(label, callback_data=f"reportreason|{target_id}|{code}")]
                   for code, (label, _weight) in REPORT_REASONS.items()]
        buttons.append([InlineKeyboardButton("« Back", callback_data=f"reportback|{target_id}")])
        await safe_tele_func_call(query.edit_message_text, text=REPORT_REASON_PROMPT_TEXT, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
        return


async def handle_report_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    target_id = int(query.data.split("|")[1])
    track = init.user_details.get(target_id, {}).get("feedback_track", {}).get(user_id, {"voted": False, "reported": False, "blocked": False})
    await _refresh_feedback_message(query, target_id, track)


async def handle_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    _, target_id, code = query.data.split("|")
    target_id = int(target_id)

    track = init.user_details.setdefault(target_id, {}).setdefault("feedback_track", {})
    track.setdefault(user_id, {"voted": False, "reported": False, "blocked": False})

    if not track[user_id]["reported"]:
        await file_report(user_id, target_id, code, context=context)
        track[user_id]["reported"] = True

    init.dirty_users.update([user_id, target_id])
    await safe_tele_func_call(query.edit_message_text, text=REPORT_LOGGED_TEXT, parse_mode="HTML")


async def _refresh_feedback_message(query, target_id: int, track_for_user: dict):
    voted = track_for_user.get("voted", False)
    reported = track_for_user.get("reported", False)
    blocked = track_for_user.get("blocked", False)

    if voted and reported and blocked:
        await safe_tele_func_call(query.edit_message_text, text=FEEDBACK_THANKS_TEXT, parse_mode="HTML")
    else:
        markup = _feedback_keyboard(target_id, voted, reported, blocked)
        await safe_tele_func_call(query.edit_message_text, text=RATE_PROMPT_TEXT, reply_markup=markup, parse_mode="HTML")
