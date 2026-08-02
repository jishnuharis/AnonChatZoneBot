from saveNload import load_user_data  # Importing to load the user data into the db when the program starts

import os  # Importing to help us get the desired constants from a separate file
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Holds the Bot Token
OWNER = os.getenv("OWNER")  # Holds the owner's ID

# Extra admins besides OWNER, comma separated user ids e.g. "111,222,333"
ADMIN_IDS = set()
_admin_env = os.getenv("ADMIN_IDS", "")
for _piece in _admin_env.split(","):
    _piece = _piece.strip()
    if _piece.isdigit():
        ADMIN_IDS.add(int(_piece))

waiting_users = []  # Holds the IDs of the users waiting for a partner
wait_started = {}  # user_id -> timestamp they joined the queue (used for matchmaking grace period)
active_pairs = {}  # Holds the pairs of users' IDs where user's ID is the key and  the partner's ID is the value

# Preference tags, bit index = position in this list
PREFERENCE_TAGS = [
    ("Gaming", "🎮"),
    ("Anime", "🍥"),
    ("Flirting", "💋"),
    ("Music", "🎵"),
    ("Movies", "🎬"),
    ("Sports", "⚽"),
    ("Memes", "😂"),
    ("Relationships", "❤️"),
    ("Study", "📚"),
    ("Politics", "🏛️"),
]


def _default_user():
    return {
        "gender": None,
        "age": None,
        "country": None,
        "preferences": 0,
        "reports": 0,
        "reporters": [],
        "votes": {"up": 0, "down": 0},
        "voters": [],
        "feedback_track": {},
        "partner_id": None,
        "points": 0,
        "restricted_until": None,
        "restriction_reason": None,
        "severity_score": 0,
        "report_log": [],
        "last_severity_decay": time.time(),
        # Subscription: None = never subscribed / lapsed. A timestamp means the
        # subscription is valid until that time - subscription.is_subscribed()
        # is the single source of truth, nothing else should be checked directly.
        "subscription_expires": None,
        "subscription_tier": None,
        # Daily /next usage tracking - reset whenever next_used_day no longer
        # matches today's date (see subscription.py).
        "next_used_today": 0,
        "next_used_day": None,
    }


user_details = {int(k): v for k, v in load_user_data().items()}  # Holds the users' details and ratings
for user_id, details in user_details.items():
    # Backfill any keys missing from older saves so nothing KeyErrors later
    for key, value in _default_user().items():
        details.setdefault(key, value)
    if details["partner_id"] and user_id not in active_pairs:
        active_pairs[user_id] = details["partner_id"]

user_input_stage = {}  # Track the current input stage the user is in
edit_stage = {}  # Track which field the user is editing
dirty_users = set()

game_requests = {}  # partner_id -> {"from": requester_id, "game": game_type}

# Privacy Mode media held server-side until the recipient opens it (or it expires)
pending_media = {}  # token -> {sender, recipient, kind, file_id, caption, created_at, opened}

# Maps a message the user sees in their own chat to the corresponding message in their
# partner's chat, so replies and reactions can be mirrored across the relay.
# user_id -> {local_message_id: (partner_id, partner_message_id)}
message_map = {}
