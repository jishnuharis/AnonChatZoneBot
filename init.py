import os
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER = os.getenv("OWNER")

ADMIN_IDS = set()
_admin_env = os.getenv("ADMIN_IDS", "")
for _piece in _admin_env.split(","):
    _piece = _piece.strip()
    if _piece.isdigit():
        ADMIN_IDS.add(int(_piece))

waiting_users = []
wait_started = {}
active_pairs = {}

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

        "subscription_expires": None,
        "subscription_tier": None,

        "daily_credits_used": 0,
        "daily_credits_reset_day": None,

        "referred_by": None,
        "referral_count": 0,
        "referral_rewarded_count": 0,
        "referral_credited": False,
    }


# These start empty and are populated by `await load_all()` during bot
# startup (see main.py on_startup), since the DB driver is now async and
# can no longer be queried at plain module-import time.
user_details = {}

user_input_stage = {}
edit_stage = {}
dirty_users = set()

game_requests = {}

pending_media = {}

message_map = {}

referral_scheme = {"required_referrals": 0, "expires": None}


async def load_all():
    """Populate user_details, active_pairs, and referral_scheme from the DB.
    Must be awaited once during startup, before the bot starts polling."""
    from saveNload import load_user_data, load_config

    global referral_scheme

    loaded = await load_user_data()
    for k, v in loaded.items():
        user_id = int(k)
        for key, value in _default_user().items():
            v.setdefault(key, value)
        user_details[user_id] = v
        if v["partner_id"] and user_id not in active_pairs:
            active_pairs[user_id] = v["partner_id"]

    referral_scheme = await load_config("referral_scheme") or {"required_referrals": 0, "expires": None}
