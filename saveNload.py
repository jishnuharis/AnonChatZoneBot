import json
import os

from psycopg_pool import AsyncConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL")

pool = AsyncConnectionPool(DATABASE_URL, min_size=1, max_size=5, open=False)


async def init_pool():
    await pool.open()
    await ensure_db()


async def close_pool():
    await pool.close()


async def ensure_db():
    async with pool.connection() as conn:
        await conn.execute("""
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
                    points INTEGER,
                    preferences INTEGER,
                    restricted_until DOUBLE PRECISION,
                    restriction_reason TEXT,
                    severity_score INTEGER,
                    report_log JSONB,
                    last_severity_decay DOUBLE PRECISION,
                    subscription_expires DOUBLE PRECISION,
                    subscription_tier VARCHAR(25),
                    daily_credits_used INTEGER,
                    daily_credits_reset_day VARCHAR(10),
                    referred_by BIGINT,
                    referral_count INTEGER,
                    referral_rewarded_count INTEGER,
                    referral_credited BOOLEAN
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_config (
                    key VARCHAR(64) PRIMARY KEY,
                    value JSONB
            )
        """)


async def load_config(key: str):
    async with pool.connection() as conn:
        cursor = await conn.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def save_config(key: str, value: dict):
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO bot_config (key, value) VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, json.dumps(value)),
        )


async def save_user_data(data: dict, dirty_user: set):
    QUERY = """
            INSERT INTO user_details (
                user_id, gender, age, country, reports, reporters,
                vote_up, vote_down, voters, feedback_track, partner_id, points,
                preferences, restricted_until, restriction_reason, severity_score,
                report_log, last_severity_decay, subscription_expires, subscription_tier,
                daily_credits_used, daily_credits_reset_day, referred_by, referral_count,
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
                daily_credits_used = EXCLUDED.daily_credits_used,
                daily_credits_reset_day = EXCLUDED.daily_credits_reset_day,
                referred_by = EXCLUDED.referred_by,
                referral_count = EXCLUDED.referral_count,
                referral_rewarded_count = EXCLUDED.referral_rewarded_count,
                referral_credited = EXCLUDED.referral_credited
    """

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
            details.get("daily_credits_used", 0),
            details.get("daily_credits_reset_day"),
            details.get("referred_by"),
            details.get("referral_count", 0),
            details.get("referral_rewarded_count", 0),
            details.get("referral_credited", False),
        ))

    async with pool.connection() as conn:
        async with conn.cursor() as cursor:
            if values:
                await cursor.executemany(QUERY, values)
                print(f"✅ User Data Saved to Drive Successfully. Updated Data of {len(dirty_user)} Users.")
            else:
                await cursor.execute("SELECT 1")

    dirty_user.clear()


async def load_user_data() -> dict:
    async with pool.connection() as conn:
        cursor = await conn.execute("""
            SELECT user_id, gender, age, country, reports, reporters, vote_up, vote_down,
                   voters, feedback_track, partner_id, points, preferences, restricted_until,
                   restriction_reason, severity_score, report_log, last_severity_decay,
                   subscription_expires, subscription_tier, daily_credits_used, daily_credits_reset_day,
                   referred_by, referral_count, referral_rewarded_count, referral_credited
            FROM user_details
        """)
        rows = await cursor.fetchall()

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
                "daily_credits_used": row[20] or 0,
                "daily_credits_reset_day": row[21],
                "referred_by": row[22],
                "referral_count": row[23] or 0,
                "referral_rewarded_count": row[24] or 0,
                "referral_credited": bool(row[25]),
            }
        return data
