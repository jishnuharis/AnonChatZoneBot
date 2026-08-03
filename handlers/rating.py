from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from moderation import REPORT_REASONS, file_report
from message import RATE_PROMPT_TEXT, REPORT_REASON_PROMPT_TEXT, REPORT_LOGGED_TEXT, FEEDBACK_THANKS_TEXT

import init
import referral


def _feedback_keyboard(to_id, voted, reported):
    buttons = []
    if not voted:
        buttons.append([InlineKeyboardButton("👍", callback_data=f"rate|{to_id}|up"),
                         InlineKeyboardButton("👎", callback_data=f"rate|{to_id}|down")])
    if not reported:
        buttons.append([InlineKeyboardButton("🚩 Report", callback_data=f"report|{to_id}")])
    return InlineKeyboardMarkup(buttons)


async def ask_for_rating(bot, from_id, to_id):
    markup = _feedback_keyboard(to_id, voted=False, reported=False)
    init.user_details[to_id].setdefault("feedback_track", {})
    init.user_details[to_id]["feedback_track"][from_id] = {"voted": False, "reported": False}
    await safe_tele_func_call(bot.send_message, chat_id=from_id, text=RATE_PROMPT_TEXT,
                               reply_markup=markup, parse_mode="HTML")

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
    if target_id not in init.user_details:
        from init import _default_user
        init.user_details[target_id] = _default_user()

    track = init.user_details[target_id].setdefault("feedback_track", {})
    track.setdefault(user_id, {"voted": False, "reported": False})

    if action == "rate":
        vote_type = data[2]
        if not track[user_id]["voted"]:
            if user_id not in init.user_details[target_id]["voters"]:
                init.user_details[target_id]["votes"][vote_type] += 1
                init.user_details[target_id]["voters"].append(user_id)
            track[user_id]["voted"] = True
        init.dirty_users.update([user_id, target_id])
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
    track = init.user_details.get(target_id, {}).get("feedback_track", {}).get(user_id, {"voted": False, "reported": False})
    await _refresh_feedback_message(query, target_id, track)


async def handle_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    _, target_id, code = query.data.split("|")
    target_id = int(target_id)

    if target_id not in init.user_details:
        from init import _default_user
        init.user_details[target_id] = _default_user()

    track = init.user_details[target_id].setdefault("feedback_track", {})
    track.setdefault(user_id, {"voted": False, "reported": False})

    if not track[user_id]["reported"]:
        if user_id not in init.user_details[target_id]["reporters"]:
            init.user_details[target_id]["reporters"].append(user_id)
            file_report(user_id, target_id, code)
        track[user_id]["reported"] = True

    init.dirty_users.update([user_id, target_id])
    await safe_tele_func_call(query.edit_message_text, text=REPORT_LOGGED_TEXT, parse_mode="HTML")


async def _refresh_feedback_message(query, target_id, track_for_user):
    voted = track_for_user["voted"]
    reported = track_for_user["reported"]
    user_id = query.from_user.id
    if voted and reported:
        del init.user_details[target_id]["feedback_track"][user_id]
        await safe_tele_func_call(query.edit_message_text, text=FEEDBACK_THANKS_TEXT, parse_mode="HTML")
    else:
        await safe_tele_func_call(query.edit_message_text, text=RATE_PROMPT_TEXT, reply_markup=_feedback_keyboard(target_id, voted, reported), parse_mode="HTML")
