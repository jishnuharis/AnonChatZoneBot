from saveNload import load_user_data  # Importing to load the user data into the db when the program starts

import os  # Importing to help us get the desired constants from a separate file

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Holds the Bot Token
OWNER = os.getenv("OWNER")  # Holds the owner's ID

waiting_users = []  # Holds the IDs of the users waiting for a partner
active_pairs = {}  # Holds the pairs of users' IDs where user's ID is the key and  the partner's ID is the value
user_details = {int(k): v for k, v in load_user_data().items()}  # Holds the users' details and ratings
for user_id, details in user_details.items():
    if details["partner_id"] and user_id not in active_pairs:
        active_pairs[user_id] = details["partner_id"]
user_input_stage = {}  # Track the current input stage the user is in
edit_stage = {}  # Track which field the user is editing
