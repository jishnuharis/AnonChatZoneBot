import os
import time
import asyncio
from typing import Dict, Any, Set, List

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER = os.getenv("OWNER")

ADMIN_IDS: Set[int] = set()
_admin_env = os.getenv("ADMIN_IDS", "")
for _piece in _admin_env.split(","):
    _piece = _piece.strip()
    if _piece.isdigit():
        ADMIN_IDS.add(int(_piece))

# Concurrency-safe queue lock
queue_lock = asyncio.Lock()

waiting_users: List[int] = []
wait_started: Dict[int, float] = {}
active_pairs: Dict[int, int] = {}
active_sessions: Dict[int, str] = {}  # user_id -> session_uuid
recent_partners: Dict[int, List[int]] = {}  # user_id -> list of recent partner IDs
last_activity: Dict[int, float] = {}  # user_id -> timestamp of last in-chat action

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


def _default_user() -> Dict[str, Any]:
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

        "pref_gender": "ANY",  # Paid filter: "ANY", "M", "F"
        "pref_country": "ANY",  # Paid filter: "ANY", "SAME", or country name

        "referred_by": None,
        "referral_count": 0,
        "referral_rewarded_count": 0,
        "referral_credited": False,
    }


# In-memory working cache for active users
user_details: Dict[int, Dict[str, Any]] = {}

user_input_stage: Dict[int, str] = {}
edit_stage: Dict[int, str] = {}
dirty_users: Set[int] = set()

game_requests: Dict[int, Dict[str, Any]] = {}
pending_media: Dict[str, Dict[str, Any]] = {}
message_map: Dict[int, Dict[int, tuple]] = {}

referral_scheme: Dict[str, Any] = {"required_referrals": 0, "expires": None}


async def load_all():
    """Populate active user cache and referral scheme from the DB on startup."""
    from saveNload import load_user_data, load_config, get_user

    global referral_scheme

    loaded = await load_user_data()
    for k, v in loaded.items():
        user_id = int(k)
        for key, value in _default_user().items():
            v.setdefault(key, value)
        user_details[user_id] = v

    referral_scheme = await load_config("referral_scheme") or {"required_referrals": 0, "expires": None}


async def ensure_user_loaded(user_id: int) -> Dict[str, Any]:
    """Ensures user data is available in memory; fetches from DB if missing."""
    if user_id in user_details:
        return user_details[user_id]
    
    from saveNload import get_user
    db_user = await get_user(user_id)
    if db_user:
        for key, value in _default_user().items():
            db_user.setdefault(key, value)
        user_details[user_id] = db_user
        return db_user
    
    default_data = _default_user()
    user_details[user_id] = default_data
    return default_data
