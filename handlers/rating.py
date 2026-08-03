# Imports everything needed from the telegram module
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from moderation import REPORT_REASONS, file_report
from message import RATE_PROMPT_TEXT, REPORT_REASON_PROMPT_TEXT, REPORT_LOGGED_TEXT, FEEDBACK_THANKS_TEXT

import init  # Importing the bot credentials and users' details
import referral


def _feedback_keyboard(to_id, voted, reported):
    buttons = []
    if not voted:
        buttons.append([InlineKeyboardButton("👍", callback_data=f"rate|{to_id}|up"),
                         InlineKeyboardButton("👎", callback_data=f"rate|{to_id}|down")])
    if not reported:
        buttons.append([InlineKeyboardButton("🚩 Report", callback_data=f"report|{to_id}")])
    return InlineKeyboardMarkup(buttons)



# Function asks for rating from the user for their partner
async def ask_for_rating(bot, from_id, to_id):
    markup = _feedback_keyboard(to_id, voted=False, reported=False)
    init.user_details[to_id].setdefault("feedback_track", {})  # Sets up the feedback_track to the partner's ID to track the users feedback
    init.user_details[to_id]["feedback_track"][from_id] = {"voted": False, "reported": False}  # Sets both voted and reported state to False initially
    await safe_tele_func_call(bot.send_message, chat_id=from_id, text=RATE_PROMPT_TEXT,
                               reply_markup=markup, parse_mode="HTML")  # Asks the user if they wanna rate their partner and shows them the menu

    # Every chat ending is also our one shot at reminding people the referral
    # program exists - maybe_announce is a no-op unless a scheme is currently
    # active, and even then only fires about 1 in 20 times.
    await referral.maybe_announce(bot, from_id)


# Handles the vote (up/down) done by the user, and kicks off the report-reason menu
async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query: CallbackQuery = update.callback_query
    await query.answer()  # Gets the query from the user input
    data = query.data.split("|")
    if not (2 <= len(data) <= 3):  # Checks if the length of the data is in desired size and breaks the function if it's different
        return

    action = data[0]
    target_id = int(data[1])
    if target_id not in init.user_details:  # Checks if the target's ID is in the user database and if not present it initialises the row for the target's ID
        from init import _default_user
        init.user_details[target_id] = _default_user()

    track = init.user_details[target_id].setdefault("feedback_track", {})  # Initialises the tracker
    track.setdefault(user_id, {"voted": False, "reported": False})  # Initialises both voted and reported to False

    if action == "rate":  # Checks if the user did 'rate'
        vote_type = data[2]
        if not track[user_id]["voted"]:  # Checks if the user's ID doesn't have value of 'voted' as True in the feedback_track of the target
            if user_id not in init.user_details[target_id]["voters"]:  # Checks if the user's ID is not in the voters list of the target
                init.user_details[target_id]["votes"][vote_type] += 1  # Increments the vote up or vote down by 1
                init.user_details[target_id]["voters"].append(user_id)  # Adds the user's ID to the voters list of the target
            track[user_id]["voted"] = True  # Sets the 'voted' value of the user to True in the feedback_track of the target
        init.dirty_users.update([user_id, target_id])
        await _refresh_feedback_message(query, target_id, track[user_id])
        return

    if action == "report":  # Checks if the user wants to report, opens the reason picker
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
            # file_report logs the report and auto-restricts the target once their
            # severity score crosses a threshold - it does this quietly, with no DM
            # to the owner. A single report (even an "underage concern" one) never
            # restricts anyone on its own; it takes a real pattern of reports.
            # If a restricted user thinks it's a mistake, they can reach out to an
            # admin themselves to get it reviewed - the owner doesn't need to be
            # paged for every report that comes in.
            file_report(user_id, target_id, code)
        track[user_id]["reported"] = True

    init.dirty_users.update([user_id, target_id])
    await safe_tele_func_call(query.edit_message_text, text=REPORT_LOGGED_TEXT, parse_mode="HTML")


async def _refresh_feedback_message(query, target_id, track_for_user):
    voted = track_for_user["voted"]
    reported = track_for_user["reported"]
    user_id = query.from_user.id
    if voted and reported:  # If the user is both voted and reported it thanks the user for doing it
        del init.user_details[target_id]["feedback_track"][user_id]
        await safe_tele_func_call(query.edit_message_text, text=FEEDBACK_THANKS_TEXT, parse_mode="HTML")
    else:  # Else it shows corresponding message and buttons to keep the menu active
        await safe_tele_func_call(query.edit_message_text, text=RATE_PROMPT_TEXT, reply_markup=_feedback_keyboard(target_id, voted, reported), parse_mode="HTML")
