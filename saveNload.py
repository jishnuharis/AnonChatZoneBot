# Imports modules which handles the database
import json
import os
import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")  # Holds the database's URL


# Establishes connection between the program and the database
def get_connection():
    return psycopg2.connect(DATABASE_URL)


# Ensures the structure of the database is in the desired form and establishes it newly if it's missing
def ensure_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_details (
                    user_id BIGINT PRIMARY KEY,
                    gender VARCHAR(1),
                    age INTEGER,
                    country VARCHAR(25),
                    reports INTEGER,
                    reporters TEXT,
                    vote_up INTEGER,
                    vote_down INTEGER,
                    voters TEXT,
                    feedback_track JSONB,
                    partner_id BIGINT,
                    points INTEGER
            )
        """)
        # Referral columns, added on top of whatever's already there so existing
        # deployments don't need a manual migration - see the note above
        # save_user_data on why older columns above (preferences, subscription_*,
        # etc.) aren't listed in the CREATE TABLE itself.
        cursor.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS referred_by BIGINT")
        cursor.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS referral_count INTEGER")
        cursor.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS referral_rewarded_count INTEGER")
        cursor.execute("ALTER TABLE user_details ADD COLUMN IF NOT EXISTS referral_credited BOOLEAN")

        # Tiny global key/value store - currently just holds the admin-configured
        # referral scheme (see referral.py). Unlike user_details, this is written
        # immediately on change rather than batched through dirty_users, since
        # admin config changes are rare and should apply instantly.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                    key VARCHAR(64) PRIMARY KEY,
                    value JSONB
            )
        """)
        conn.commit()


# Reads a single bot_config row, or None if it's never been set
def load_config(key: str):
    ensure_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
        row = cursor.fetchone()
        return row[0] if row else None


# Writes a single bot_config row immediately (not batched - see ensure_db note)
def save_config(key: str, value: dict):
    ensure_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bot_config (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, json.dumps(value)),
        )
        conn.commit()


# Function which stores the details of the users in the database
def save_user_data(data: dict, dirty_user: set):
    ensure_db()

    QUERY = """
            INSERT INTO user_details (
                user_id, gender, age, country, reports, reporters,
                vote_up, vote_down, voters, feedback_track, partner_id, points,
                preferences, restricted_until, restriction_reason, severity_score,
                report_log, last_severity_decay, subscription_expires, subscription_tier,
                next_used_today, next_used_day, referred_by, referral_count,
                referral_rewarded_count, referral_credited
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                gender = EXCLUDED.gender,
                age = EXCLUDED.age,
                country = EXCLUDED.country,
                reports = EXCLUDED.reports,
                reporters = EXCLUDED.reporters,
                vote_up = EXCLUDED.vote_up,
                vote_down = EXCLUDED.vote_down,
                voters = EXCLUDED.voters,
                feedback_track = EXCLUDED.feedback_track,
                partner_id = EXCLUDED.partner_id,
                points = EXCLUDED.points,
                preferences = EXCLUDED.preferences,
                restricted_until = EXCLUDED.restricted_until,
                restriction_reason = EXCLUDED.restriction_reason,
                severity_score = EXCLUDED.severity_score,
                report_log = EXCLUDED.report_log,
                last_severity_decay = EXCLUDED.last_severity_decay,
                subscription_expires = EXCLUDED.subscription_expires,
                subscription_tier = EXCLUDED.subscription_tier,
                next_used_today = EXCLUDED.next_used_today,
                next_used_day = EXCLUDED.next_used_day,
                referred_by = EXCLUDED.referred_by,
                referral_count = EXCLUDED.referral_count,
                referral_rewarded_count = EXCLUDED.referral_rewarded_count,
                referral_credited = EXCLUDED.referral_credited
    """

    with get_connection() as conn:
        cursor = conn.cursor()

        values = []

        for user_id in list(dirty_user):
            details = data.get(user_id)
            if details is None:
                continue

            values.append((
                user_id,
                details.get("gender"),
                details.get("age"),
                details.get("country"),
                details.get("reports", 0),
                json.dumps(details.get("reporters", [])),
                details.get("votes", {}).get("up", 0),
                details.get("votes", {}).get("down", 0),
                json.dumps(details.get("voters", [])),
                json.dumps(details.get("feedback_track", {})),
                details.get("partner_id", None),
                details.get("points", 0),
                details.get("preferences", 0),
                details.get("restricted_until"),
                details.get("restriction_reason"),
                details.get("severity_score", 0),
                json.dumps(details.get("report_log", [])),
                details.get("last_severity_decay"),
                details.get("subscription_expires"),
                details.get("subscription_tier"),
                details.get("next_used_today", 0),
                details.get("next_used_day"),
                details.get("referred_by"),
                details.get("referral_count", 0),
                details.get("referral_rewarded_count", 0),
                details.get("referral_credited", False),
            ))

        if values:
            print(f"✅ User Data Saved to Drive Successfully. Updated Data of {len(dirty_user)} Users.")
            cursor.executemany(QUERY, values)

        conn.commit()
        dirty_user.clear()


# Function which returns the users' details it read from the database
def load_user_data() -> dict:
    ensure_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, gender, age, country, reports, reporters, vote_up, vote_down,
                   voters, feedback_track, partner_id, points, preferences, restricted_until,
                   restriction_reason, severity_score, report_log, last_severity_decay,
                   subscription_expires, subscription_tier, next_used_today, next_used_day,
                   referred_by, referral_count, referral_rewarded_count, referral_credited
            FROM user_details
        """)
        rows = cursor.fetchall()

        data = {}
        for row in rows:
            user_id = row[0]
            data[user_id] = {
                "gender": row[1],
                "age": row[2],
                "country": row[3],
                "reports": row[4] or 0,
                "reporters": json.loads(row[5]) if row[5] else [],
                "votes": {
                    "up": row[6] or 0,
                    "down": row[7] or 0,
                },
                "voters": json.loads(row[8]) if row[8] else [],
                "feedback_track": row[9] or {},
                "partner_id": row[10],
                "points": row[11] or 0,
                "preferences": row[12] or 0,
                "restricted_until": row[13],
                "restriction_reason": row[14],
                "severity_score": row[15] or 0,
                "report_log": row[16] if row[16] else [],
                "last_severity_decay": row[17],
                "subscription_expires": row[18],
                "subscription_tier": row[19],
                "next_used_today": row[20] or 0,
                "next_used_day": row[21],
                "referred_by": row[22],
                "referral_count": row[23] or 0,
                "referral_rewarded_count": row[24] or 0,
                "referral_credited": bool(row[25]),
            }
        return data
