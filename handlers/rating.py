# Imports everything needed from the telegram module
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes

from security import safe_tele_func_call

import init  # Importing the bot credentials and users' details


# Function asks for rating from the user for their partner
async def ask_for_rating(bot, from_id, to_id):
    keyboard = [
        [
            InlineKeyboardButton("👍", callback_data=f"rate|{to_id}|up"),
            InlineKeyboardButton("👎", callback_data=f"rate|{to_id}|down")
        ],
        [
            InlineKeyboardButton("🚩 Report", callback_data=f"report|{to_id}")
        ]
    ]  # Initialises the keyboard with the voting up and voting down button and a report button
    markup = InlineKeyboardMarkup(keyboard)
    init.user_details[to_id].setdefault("feedback_track", {})  # Sets up the feedback_track to the partner's ID to track the users feedback
    init.user_details[to_id]["feedback_track"][from_id] = {"voted": False, "reported": False}  # Sets both voted and reported state to False initially
    await safe_tele_func_call(bot.send_message, chat_id=from_id,
                              text="""💡 *If the interlocutor misbehaved or violated the rules, send a complaint against them.*
Give a rating to the interlocutor which will affect their ratings.""",
                              reply_markup=markup, parse_mode="Markdown")  # Asks the user if they wanna rate their partner and shows them the menu


# Handles the vote and report done by the user
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
        init.user_details[target_id] = {
            "gender": None, "age": None, "country": None,
            "reports": 0, "reporters": [], "votes": {"up": 0, "down": 0},
            "voters": [], "feedback_track": {}
        }

    track = init.user_details[target_id].setdefault("feedback_track", {})  # Initialises the tracker
    track.setdefault(user_id, {"voted": False, "reported": False})  # Initialises both voted and reported to False

    if action == "rate":  # Checks if the user did 'rate'
        vote_type = data[2]
        if not track[user_id]["voted"]:  # Checks if the user's ID doesn't have value of 'voted' as True in the feedback_track of the target
            if user_id not in init.user_details[target_id]["voters"]:  # Checks if the user's ID is not in the voters list of the target
                init.user_details[target_id]["votes"][vote_type] += 1  # Increments the vote up or vote down by 1
                init.user_details[target_id]["voters"].append(user_id)  # Adds the user's ID to the voters list of the target
            track[user_id]["voted"] = True  # Sets the 'voted' value of the user to True in the feedback_track of the target
    elif action == "report":  # Checks if the user did 'vote'
        if not track[user_id]["reported"]:  # Checks if the user's ID doesn't have value of 'reported' as True in the feedback_track of the target
            if user_id not in init.user_details[target_id]["reporters"]:  # Checks if the user's ID is not in the reporters list of the target
                init.user_details[target_id]["reports"] += 1  # Increments the reports by 1
                init.user_details[target_id]["reporters"].append(user_id)  # Adds the user's ID to the reporters list of the target
            track[user_id]["reported"] = True  # Sets the 'reported' value of the user to True in the feedback_track of the target

    voted = track[user_id]["voted"]
    reported = track[user_id]["reported"]

    if (voted and reported) or (not voted and not reported):
        del init.user_details[target_id]["feedback_track"][user_id]  # If both voted and reported are True or both are False
    if voted and reported:  # If the user is both voted and reported it thanks the user for doing it
        await safe_tele_func_call(query.edit_message_text, text="*Thank You for your feedback.\nYour feedback helps other users to be safe and secure.*", parse_mode="Markdown")
    else:  # Else it shows corresponding message and buttons to keep the menu active
        buttons = []
        rate_text = "💡 If the interlocutor misbehaved or violated the rules, send a complaint against them."
        if not voted:
            buttons.append([InlineKeyboardButton("👍", callback_data=f"rate|{target_id}|up"),
                            InlineKeyboardButton("👎", callback_data=f"rate|{target_id}|down")])
        if not reported:
            buttons.append([InlineKeyboardButton("🚩 Report", callback_data=f"report|{target_id}")])
        await safe_tele_func_call(query.edit_message_text, text=f"*{rate_text}*", reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
    
    init.dirty_users.update([user_id, target_id])
