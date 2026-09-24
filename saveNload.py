import os
import json
import logging
import uuid
import time
from typing import Dict, Any, Optional, List, Set, Tuple
from datetime import datetime, date, timezone
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from migrations import run_migrations
import init

logger = logging.getLogger(__name__)

# Connection pool sizing calibrated for 500k+ users
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN", "5"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX", "30"))

pool: Optional[AsyncConnectionPool] = None


def get_pool() -> AsyncConnectionPool:
    global pool
    if pool is None:
        db_url = os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/anonchat"
        pool = AsyncConnectionPool(
            db_url,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            timeout=30.0,
            kwargs={
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5,
            },
            check=AsyncConnectionPool.check_connection,
            open=False
        )
    return pool


def is_pool_ready() -> bool:
    """Returns True if the connection pool is initialized, open, and ready for queries."""
    global pool
    return pool is not None and not pool.closed and getattr(pool, "_opened", False)


async def init_pool():
    """Initializes the database connection pool and runs schema migrations."""
    p = get_pool()
    try:
        if not getattr(p, "_opened", False):
            await p.open()
        logger.info("Database connection pool opened successfully.")
        await ensure_db()
    except Exception as e:
        logger.error(f"Database connection pool open / ensure_db notice: {e}", exc_info=True)


async def close_pool():
    """Gracefully closes all database connections in the pool."""
    global pool
    if pool is not None and getattr(pool, "_opened", False):
        await pool.close()
        logger.info("Database connection pool closed.")


async def ensure_db():
    """Applies schema migrations and table initializations."""
    p = get_pool()
    if not getattr(p, "_opened", False):
        try:
            await p.open()
        except Exception:
            pass
    try:
        async with p.connection() as conn:
            await run_migrations(conn)
    except Exception as e:
        logger.error(f"Error during ensure_db / migration: {e}", exc_info=True)
        raise


async def ping_db() -> bool:
    """
    Heartbeat ping query (SELECT 1) to keep the database and connection pool active.
    Prevents cloud-hosted databases (e.g. Railway, Neon, Supabase) from sleeping during inactivity.
    """
    if not is_pool_ready():
        return False
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("SELECT 1;")
            logger.debug("Database heartbeat ping sent successfully.")
            return True
    except Exception as e:
        logger.warning(f"Database heartbeat ping failed: {e}")
        return False


# ============================================================================
# User Core & Profile Data Operations
# ============================================================================

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user core profile, stats, moderation state, and subscription."""
    if not is_pool_ready():
        return None
    p = get_pool()
    query = """
        SELECT 
            u.user_id, u.gender, u.age, u.country, u.preferences_bitmask as preferences, u.points,
            p.severity_score, p.restricted_until, p.restriction_reason, p.last_severity_decay,
            p.daily_credits_used, p.daily_credits_reset_day, p.is_banned,
            COALESCE(p.preferred_gender, 'ANY') as pref_gender,
            COALESCE(p.preferred_country, 'ANY') as pref_country,
            s.tier as subscription_tier, s.expires_at as subscription_expires,
            GREATEST(COALESCE(p.votes_up, 0), COALESCE(r_up.votes_up, 0)) as votes_up,
            GREATEST(COALESCE(p.votes_down, 0), COALESCE(r_down.votes_down, 0)) as votes_down,
            GREATEST(COALESCE(p.reports_count, 0), COALESCE(rep.reports_count, 0)) as reports_count,
            COALESCE(p.report_log, '[]'::jsonb) as report_log,
            ref.referrer_id as referred_by,
            ref.credited as referral_credited,
            COALESCE(ref_count.total_referrals, 0) as referral_count,
            COALESCE(ref_rewarded.rewarded_referrals, 0) as referral_rewarded_count
        FROM users u
        LEFT JOIN user_profiles p ON u.user_id = p.user_id
        LEFT JOIN (
            SELECT user_id, tier, expires_at 
            FROM subscriptions 
            WHERE is_active = TRUE AND expires_at > NOW() 
            ORDER BY expires_at DESC LIMIT 1
        ) s ON u.user_id = s.user_id
        LEFT JOIN (
            SELECT target_id, COUNT(*) as votes_up 
            FROM user_ratings WHERE vote_type = 'up' GROUP BY target_id
        ) r_up ON u.user_id = r_up.target_id
        LEFT JOIN (
            SELECT target_id, COUNT(*) as votes_down 
            FROM user_ratings WHERE vote_type = 'down' GROUP BY target_id
        ) r_down ON u.user_id = r_down.target_id
        LEFT JOIN (
            SELECT target_id, COUNT(*) as reports_count 
            FROM user_reports GROUP BY target_id
        ) rep ON u.user_id = rep.target_id
        LEFT JOIN referrals ref ON u.user_id = ref.referred_id
        LEFT JOIN (
            SELECT referrer_id, COUNT(*) as total_referrals 
            FROM referrals WHERE credited = TRUE GROUP BY referrer_id
        ) ref_count ON u.user_id = ref_count.referrer_id
        LEFT JOIN (
            SELECT referrer_id, COUNT(*) as rewarded_referrals 
            FROM referrals WHERE rewarded = TRUE GROUP BY referrer_id
        ) ref_rewarded ON u.user_id = ref_rewarded.referrer_id
        WHERE u.user_id = %s;
    """
    try:
        async with p.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, (user_id,))
                row = await cur.fetchone()
                if not row:
                    legacy_user = await _get_legacy_user(conn, user_id)
                    if legacy_user:
                        return legacy_user
                    return None
                
                # Map into application-friendly dict structure
                restricted_epoch = row["restricted_until"].timestamp() if row["restricted_until"] else None
                sub_epoch = row["subscription_expires"].timestamp() if row["subscription_expires"] else None
                decay_epoch = row["last_severity_decay"].timestamp() if row["last_severity_decay"] else None

                rep_log = row.get("report_log")
                if isinstance(rep_log, str):
                    try:
                        rep_log = json.loads(rep_log)
                    except Exception:
                        rep_log = []
                elif not isinstance(rep_log, list):
                    rep_log = []

                return {
                    "user_id": row["user_id"],
                    "gender": row["gender"],
                    "age": row["age"],
                    "country": row["country"],
                    "preferences": row["preferences"] or 0,
                    "points": row["points"] or 0,
                    "severity_score": row["severity_score"] or 0,
                    "restricted_until": restricted_epoch,
                    "restriction_reason": row["restriction_reason"],
                    "is_banned": bool(row["is_banned"]),
                    "last_severity_decay": decay_epoch,
                    "daily_credits_used": row["daily_credits_used"] or 0,
                    "daily_credits_reset_day": str(row["daily_credits_reset_day"]),
                    "pref_gender": row.get("pref_gender") or "ANY",
                    "pref_country": row.get("pref_country") or "ANY",
                    "subscription_tier": row["subscription_tier"],
                    "subscription_expires": sub_epoch,
                    "votes": {"up": row["votes_up"], "down": row["votes_down"]},
                    "reports": row["reports_count"],
                    "report_log": rep_log,
                    "referred_by": row["referred_by"],
                    "referral_credited": bool(row["referral_credited"]),
                    "referral_count": row["referral_count"],
                    "referral_rewarded_count": row["referral_rewarded_count"],
                    "partner_id": None, # Session state managed via session_manager
                }
    except Exception as e:
        logger.warning(f"get_user({user_id}) error: {e}")
        return None


async def upsert_user(user_id: int, **kwargs):
    """Inserts or updates a user core and profile record."""
    if not is_pool_ready():
        return
    p = get_pool()
    try:
        async with p.connection() as conn:
            async with conn.transaction():
                # 1. Upsert users table
                user_cols = ["gender", "age", "country", "preferences", "points"]
                set_clauses = []
                values = [user_id]
                for col in user_cols:
                    if col in kwargs:
                        db_col = "preferences_bitmask" if col == "preferences" else col
                        set_clauses.append(f"{db_col} = EXCLUDED.{db_col}")

                await conn.execute("""
                    INSERT INTO users (user_id, gender, age, country, preferences_bitmask, points)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        gender = COALESCE(EXCLUDED.gender, users.gender),
                        age = COALESCE(EXCLUDED.age, users.age),
                        country = COALESCE(EXCLUDED.country, users.country),
                        preferences_bitmask = COALESCE(EXCLUDED.preferences_bitmask, users.preferences_bitmask),
                        points = COALESCE(EXCLUDED.points, users.points),
                        updated_at = NOW();
                """, (
                    user_id,
                    kwargs.get("gender"),
                    kwargs.get("age"),
                    kwargs.get("country"),
                    kwargs.get("preferences", 0),
                    kwargs.get("points", 0),
                ))

                # 2. Upsert user_profiles table
                restricted_dt = datetime.fromtimestamp(kwargs["restricted_until"], timezone.utc) if kwargs.get("restricted_until") else None
                reset_day = kwargs.get("daily_credits_reset_day")
                if isinstance(reset_day, str):
                    try:
                        reset_day = datetime.strptime(reset_day, "%Y-%m-%d").date()
                    except ValueError:
                        reset_day = date.today()

                votes_val = kwargs.get("votes")
                if isinstance(votes_val, dict):
                    v_up = votes_val.get("up", 0)
                    v_down = votes_val.get("down", 0)
                else:
                    v_up = kwargs.get("votes_up", 0)
                    v_down = kwargs.get("votes_down", 0)

                rep_count = kwargs.get("reports", kwargs.get("reports_count", 0))

                rep_log = kwargs.get("report_log")
                if not isinstance(rep_log, list):
                    rep_log = []
                rep_log_json = json.dumps(rep_log)

                await conn.execute("""
                    INSERT INTO user_profiles (
                        user_id, severity_score, restricted_until, restriction_reason,
                        daily_credits_used, daily_credits_reset_day, is_banned,
                        preferred_gender, preferred_country,
                        votes_up, votes_down, reports_count, report_log
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (user_id) DO UPDATE SET
                        severity_score = COALESCE(EXCLUDED.severity_score, user_profiles.severity_score),
                        restricted_until = EXCLUDED.restricted_until,
                        restriction_reason = EXCLUDED.restriction_reason,
                        daily_credits_used = COALESCE(EXCLUDED.daily_credits_used, user_profiles.daily_credits_used),
                        daily_credits_reset_day = COALESCE(EXCLUDED.daily_credits_reset_day, user_profiles.daily_credits_reset_day),
                        is_banned = COALESCE(EXCLUDED.is_banned, user_profiles.is_banned),
                        preferred_gender = COALESCE(EXCLUDED.preferred_gender, user_profiles.preferred_gender),
                        preferred_country = COALESCE(EXCLUDED.preferred_country, user_profiles.preferred_country),
                        votes_up = GREATEST(COALESCE(EXCLUDED.votes_up, 0), user_profiles.votes_up),
                        votes_down = GREATEST(COALESCE(EXCLUDED.votes_down, 0), user_profiles.votes_down),
                        reports_count = GREATEST(COALESCE(EXCLUDED.reports_count, 0), user_profiles.reports_count),
                        report_log = CASE 
                            WHEN EXCLUDED.report_log IS NOT NULL AND EXCLUDED.report_log != '[]'::jsonb 
                            THEN EXCLUDED.report_log 
                            ELSE user_profiles.report_log 
                        END;
                """, (
                    user_id,
                    kwargs.get("severity_score", 0),
                    restricted_dt,
                    kwargs.get("restriction_reason"),
                    kwargs.get("daily_credits_used", 0),
                    reset_day or date.today(),
                    kwargs.get("is_banned", False),
                    kwargs.get("pref_gender", "ANY"),
                    kwargs.get("pref_country", "ANY"),
                    v_up,
                    v_down,
                    rep_count,
                    rep_log_json,
                ))
    except Exception as e:
        logger.warning(f"upsert_user({user_id}) error: {e}")


# ============================================================================
# Blocking & Moderation (Ban/Block Multi-Layer Enforcement)
# ============================================================================

BLOCK_EXPIRY_SECONDS = 86400  # 24 hours


def _is_block_active(blocks, target_id: int, now_ts: float) -> bool:
    """Checks if a target_id block is present and within the 24-hour expiration window."""
    if isinstance(blocks, dict):
        ts = blocks.get(target_id)
        if ts is not None:
            return (now_ts - ts) < BLOCK_EXPIRY_SECONDS
        return False
    elif isinstance(blocks, (list, set)):
        return target_id in blocks
    return False


async def add_user_block(blocker_id: int, blocked_id: int) -> bool:
    """Records a 24-hour user-to-user block."""
    if blocker_id == blocked_id:
        return False
    now_ts = time.time()
    # Always register in local memory structure with timestamp
    init.user_details.setdefault(blocker_id, init._default_user())
    blocks = init.user_details[blocker_id].get("blocked_users")
    if not isinstance(blocks, dict):
        new_blocks = {uid: now_ts for uid in (blocks or [])}
        init.user_details[blocker_id]["blocked_users"] = new_blocks
        blocks = new_blocks
    blocks[blocked_id] = now_ts
    init.dirty_users.add(blocker_id)

    if not is_pool_ready():
        return True
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                INSERT INTO user_blocks (blocker_id, blocked_id, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (blocker_id, blocked_id) DO UPDATE SET
                    created_at = NOW()
                RETURNING id;
            """, (blocker_id, blocked_id))
            row = await cur.fetchone()
            return bool(row)
    except Exception as e:
        logger.warning(f"add_user_block error: {e}")
        return True


async def is_blocked_pairwise(u1: int, u2: int) -> bool:
    """Checks if either user has blocked the other within the last 24 hours."""
    now_ts = time.time()
    u1_blocks = init.user_details.get(u1, {}).get("blocked_users")
    u2_blocks = init.user_details.get(u2, {}).get("blocked_users")
    if _is_block_active(u1_blocks, u2, now_ts) or _is_block_active(u2_blocks, u1, now_ts):
        return True
    if not is_pool_ready():
        return False
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                SELECT 1 FROM user_blocks 
                WHERE ((blocker_id = %s AND blocked_id = %s)
                   OR (blocker_id = %s AND blocked_id = %s))
                  AND created_at > NOW() - INTERVAL '24 hours'
                LIMIT 1;
            """, (u1, u2, u2, u1))
            return bool(await cur.fetchone())
    except Exception as e:
        logger.warning(f"is_blocked_pairwise error: {e}")
        return False


async def get_blocked_users_for(user_id: int) -> List[int]:
    """Retrieves all active user IDs blocked by or that blocked the given user within the last 24 hours."""
    now_ts = time.time()
    raw_blocks = init.user_details.get(user_id, {}).get("blocked_users", {})
    if isinstance(raw_blocks, dict):
        mem_blocks = {uid for uid, ts in raw_blocks.items() if (now_ts - ts) < BLOCK_EXPIRY_SECONDS}
    else:
        mem_blocks = set(raw_blocks)

    if not is_pool_ready():
        return list(mem_blocks)
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                SELECT blocked_id FROM user_blocks 
                WHERE blocker_id = %s AND created_at > NOW() - INTERVAL '24 hours'
                UNION
                SELECT blocker_id FROM user_blocks 
                WHERE blocked_id = %s AND created_at > NOW() - INTERVAL '24 hours';
            """, (user_id, user_id))
            rows = await cur.fetchall()
            return list(mem_blocks.union({r[0] for r in rows}))
    except Exception as e:
        logger.warning(f"get_blocked_users_for error: {e}")
        return list(mem_blocks)


async def record_user_report(reporter_id: int, target_id: int, reason_code: str, weight: int):
    """Inserts a new report record."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                INSERT INTO user_reports (reporter_id, target_id, reason_code, weight)
                VALUES (%s, %s, %s, %s);
            """, (reporter_id, target_id, reason_code, weight))
    except Exception as e:
        logger.warning(f"record_user_report error: {e}")


async def record_user_rating(voter_id: int, target_id: int, vote_type: str) -> bool:
    """Records an up/down vote. Returns True if new, False if already voted."""
    if not is_pool_ready():
        return True
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                INSERT INTO user_ratings (voter_id, target_id, vote_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (voter_id, target_id) DO UPDATE SET
                    vote_type = EXCLUDED.vote_type
                RETURNING id;
            """, (voter_id, target_id, vote_type))
            return bool(await cur.fetchone())
    except Exception as e:
        logger.warning(f"record_user_rating error: {e}")
        return True


async def apply_user_restriction_db(user_id: int, until_dt: Optional[datetime], reason: str, is_banned: bool = False):
    """Sets restriction/ban timestamp on user profile."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                UPDATE user_profiles 
                SET restricted_until = %s,
                    restriction_reason = %s,
                    is_banned = %s
                WHERE user_id = %s;
            """, (until_dt, reason, is_banned, user_id))
    except Exception as e:
        logger.warning(f"apply_user_restriction_db error: {e}")


async def clear_user_restriction_db(user_id: int):
    """Clears ban / restriction from user profile."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                UPDATE user_profiles 
                SET restricted_until = NULL,
                    restriction_reason = NULL,
                    is_banned = FALSE
                WHERE user_id = %s;
            """, (user_id,))
    except Exception as e:
        logger.warning(f"clear_user_restriction_db error: {e}")


async def decay_severity_scores_sql(decay_rate: int = 1) -> int:
    """
    Executes daily severity score decay directly inside PostgreSQL in O(1) time,
    eliminating the previous O(N) memory loop across 500k users.
    """
    if not is_pool_ready():
        return 0
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                UPDATE user_profiles
                SET severity_score = GREATEST(0, severity_score - %s),
                    last_severity_decay = NOW()
                WHERE severity_score > 0
                  AND last_severity_decay < NOW() - INTERVAL '1 day'
                RETURNING user_id;
            """, (decay_rate,))
            rows = await cur.fetchall()
            return len(rows)
    except Exception as e:
        logger.warning(f"decay_severity_scores_sql error: {e}")
        return 0


# ============================================================================
# Chat Session Lifecycle Management
# ============================================================================

async def create_chat_session_db(user1_id: int, user2_id: int) -> str:
    """Creates a new active chat session entry."""
    session_id = str(uuid.uuid4())
    if not is_pool_ready():
        return session_id
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                INSERT INTO chat_sessions (id, user1_id, user2_id, status, started_at)
                VALUES (%s, %s, %s, 'active', NOW());
            """, (session_id, user1_id, user2_id))
    except Exception as e:
        logger.warning(f"create_chat_session_db error: {e}")
    return session_id


async def get_active_sessions_db() -> List[Tuple[str, int, int]]:
    """Returns all currently active chat sessions from PostgreSQL or legacy fallback."""
    if not is_pool_ready():
        return []
    p = get_pool()
    try:
        async with p.connection() as conn:
            cur = await conn.execute("""
                SELECT (to_regclass('chat_sessions') IS NOT NULL);
            """)
            if (await cur.fetchone())[0]:
                cur = await conn.execute("""
                    SELECT id, user1_id, user2_id 
                    FROM chat_sessions 
                    WHERE status = 'active';
                """)
                rows = await cur.fetchall()
                if rows:
                    return [(str(r[0]), int(r[1]), int(r[2])) for r in rows]

            # Fallback to legacy table partner_id if available
            tbl = await _get_legacy_table_name(conn)
            if tbl:
                cur = await conn.execute(f"""
                    SELECT user_id, partner_id FROM {tbl} 
                    WHERE partner_id IS NOT NULL AND partner_id > 0;
                """)
                legacy_pairs = await cur.fetchall()
                seen = set()
                res = []
                for u1, u2 in legacy_pairs:
                    u1, u2 = int(u1), int(u2)
                    if u1 not in seen and u2 not in seen:
                        seen.add(u1)
                        seen.add(u2)
                        res.append((str(uuid.uuid4()), u1, u2))
                return res
    except Exception as e:
        logger.warning(f"get_active_sessions_db error: {e}")
    return []


async def end_chat_session_db(session_id: str, reason: str = "normal"):
    """Marks a chat session as ended."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                UPDATE chat_sessions
                SET status = 'ended',
                    ended_at = NOW(),
                    end_reason = %s
                WHERE id = %s AND status = 'active';
            """, (reason, session_id))
    except Exception as e:
        logger.warning(f"end_chat_session_db error: {e}")


async def update_session_activity_db(session_id: str):
    """Updates the last_activity_at timestamp for a session."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                UPDATE chat_sessions
                SET last_activity_at = NOW()
                WHERE id = %s;
            """, (session_id,))
    except Exception as e:
        logger.warning(f"update_session_activity_db error: {e}")


# ============================================================================
# Subscriptions & Payment Transactions
# ============================================================================

async def add_subscription_db(user_id: int, tier: str, duration_days: int, source: str = "purchase") -> datetime:
    """Grants or extends an active subscription, preventing tier downgrades."""
    now = datetime.now(timezone.utc)
    new_expires = now + duration_days * 86400
    if not is_pool_ready():
        return new_expires
    try:
        p = get_pool()
        async with p.connection() as conn:
            async with conn.transaction():
                # Check current active subscription expiry
                cur = await conn.execute("""
                    SELECT expires_at FROM subscriptions
                    WHERE user_id = %s AND is_active = TRUE AND expires_at > NOW()
                    ORDER BY expires_at DESC LIMIT 1;
                """, (user_id,))
                row = await cur.fetchone()
                base_time = row[0] if (row and row[0] > now) else now
                new_expires = base_time + duration_days * 86400

                await conn.execute("""
                    INSERT INTO subscriptions (user_id, tier, starts_at, expires_at, source, is_active)
                    VALUES (%s, %s, NOW(), %s, %s, TRUE);
                """, (user_id, tier, new_expires, source))
                return new_expires
    except Exception as e:
        logger.warning(f"add_subscription_db error: {e}")
        return new_expires


async def record_payment_transaction_db(user_id: int, tier: str, stars: int, charge_id: str = None) -> bool:
    """Records a Telegram Stars payment transaction with idempotency."""
    if not is_pool_ready():
        return True
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                INSERT INTO payment_transactions (user_id, tier, stars, currency, telegram_payment_charge_id)
                VALUES (%s, %s, %s, 'XTR', %s)
                RETURNING id;
            """, (user_id, tier, stars, charge_id))
            return bool(await cur.fetchone())
    except Exception as e:
        logger.warning(f"record_payment_transaction_db error: {e}")
        return True


# ============================================================================
# Promotions & Campaigns
# ============================================================================

async def get_active_promotions_db() -> List[Dict[str, Any]]:
    """Fetches currently active promotional campaigns ordered by priority."""
    if not is_pool_ready():
        return []
    try:
        p = get_pool()
        query = """
            SELECT id, title, sponsor_name, message_text, button_text, button_url,
                   priority, display_frequency, impressions_count, clicks_count
            FROM promotions
            WHERE is_active = TRUE
              AND (end_date IS NULL OR end_date > NOW())
              AND start_date <= NOW()
            ORDER BY priority DESC, created_at DESC;
        """
        async with p.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query)
                return await cur.fetchall()
    except Exception as e:
        logger.warning(f"get_active_promotions_db error: {e}")
        return []


async def increment_promo_impression_db(promo_id: int):
    """Increments impression counter for a campaign."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("UPDATE promotions SET impressions_count = impressions_count + 1 WHERE id = %s", (promo_id,))
    except Exception as e:
        logger.warning(f"increment_promo_impression_db error: {e}")


async def increment_promo_click_db(promo_id: int):
    """Increments click counter for a campaign."""
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("UPDATE promotions SET clicks_count = clicks_count + 1 WHERE id = %s", (promo_id,))
    except Exception as e:
        logger.warning(f"increment_promo_click_db error: {e}")


async def add_promotion_db(title: str, sponsor_name: str, message_text: str, button_text: str = None, button_url: str = None, priority: int = 1) -> int:
    """Adds a new sponsor campaign."""
    if not is_pool_ready():
        return 1
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                INSERT INTO promotions (title, sponsor_name, message_text, button_text, button_url, priority)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (title, sponsor_name, message_text, button_text, button_url, priority))
            row = await cur.fetchone()
            return row[0]
    except Exception as e:
        logger.warning(f"add_promotion_db error: {e}")
        return 1


# ============================================================================
# Extensible Game Questions (Would You Rather, Trivia, etc.)
# ============================================================================

async def get_game_questions_db(game_type: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves active game questions."""
    if not is_pool_ready():
        return []
    try:
        p = get_pool()
        query = """
            SELECT id, game_type, category, prompt_a, prompt_b, correct_answer
            FROM game_questions
            WHERE game_type = %s AND is_active = TRUE
        """
        params = [game_type]
        if category:
            query += " AND category = %s"
            params.append(category)
        query += " ORDER BY RANDOM() LIMIT %s;"
        params.append(limit)

        async with p.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                return await cur.fetchall()
    except Exception as e:
        logger.warning(f"get_game_questions_db error: {e}")
        return []


async def add_game_question_db(game_type: str, category: str, prompt_a: str, prompt_b: str = None, correct_answer: str = None) -> int:
    """Inserts a new data-driven game question."""
    if not is_pool_ready():
        return 1
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("""
                INSERT INTO game_questions (game_type, category, prompt_a, prompt_b, correct_answer)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (game_type, category, prompt_a, prompt_b, correct_answer))
            row = await cur.fetchone()
            return row[0]
    except Exception as e:
        logger.warning(f"add_game_question_db error: {e}")
        return 1


# ============================================================================
# Bot Configuration Key-Value Store
# ============================================================================

async def load_config(key: str) -> Optional[Any]:
    if not is_pool_ready():
        return None
    try:
        p = get_pool()
        async with p.connection() as conn:
            cur = await conn.execute("SELECT value FROM bot_config WHERE key = %s", (key,))
            row = await cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.warning(f"load_config error: {e}")
        return None


async def save_config(key: str, value: Any):
    if not is_pool_ready():
        return
    try:
        p = get_pool()
        async with p.connection() as conn:
            await conn.execute("""
                INSERT INTO bot_config (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """, (key, json.dumps(value)))
    except Exception as e:
        logger.warning(f"save_config error: {e}")


# ============================================================================
# Backward-Compatible Legacy Wrappers
# ============================================================================

async def save_user_data(data: dict, dirty_user: set):
    """
    Backward-compatible save routine.
    Flushes all dirty users using transactional upserts without dropping in-flight modifications.
    If no users are dirty, sends a heartbeat query (SELECT 1) to keep the cloud DB awake.
    """
    if not dirty_user:
        await ping_db()
        return

    to_flush = list(dirty_user)
    for uid in to_flush:
        dirty_user.discard(uid)

    for uid in to_flush:
        details = data.get(uid)
        if details:
            try:
                await upsert_user(uid, **details)
            except Exception as e:
                logger.error(f"Failed to upsert user {uid}: {e}")
                dirty_user.add(uid)


async def _get_legacy_table_name(conn) -> Optional[str]:
    """Resolves whether legacy table is named legacy_user_details_backup or user_details with records."""
    for candidate in ("legacy_user_details_backup", "user_details"):
        try:
            cur = await conn.execute(f"SELECT (to_regclass('{candidate}') IS NOT NULL);")
            if (await cur.fetchone())[0]:
                cur = await conn.execute(f"SELECT COUNT(*) FROM {candidate};")
                if (await cur.fetchone())[0] > 0:
                    return candidate
        except Exception:
            continue
    return None


async def _get_legacy_user(conn, user_id: int) -> Optional[Dict[str, Any]]:
    try:
        tbl = await _get_legacy_table_name(conn)
        if not tbl:
            return None
        cur = await conn.execute(f"""
            SELECT user_id, gender, age, country, preferences, points,
                   subscription_tier, subscription_expires,
                   COALESCE(vote_up, 0) as vote_up,
                   COALESCE(vote_down, 0) as vote_down,
                   COALESCE(reports, 0) as reports,
                   report_log
            FROM {tbl} WHERE user_id = %s;
        """, (user_id,))
        r = await cur.fetchone()
        if r:
            rep_log = r[11]
            if isinstance(rep_log, str):
                try:
                    rep_log = json.loads(rep_log)
                except Exception:
                    rep_log = []
            elif not isinstance(rep_log, list):
                rep_log = []

            return {
                "user_id": r[0],
                "gender": r[1],
                "age": r[2],
                "country": r[3],
                "preferences": r[4] or 0,
                "points": r[5] or 0,
                "subscription_tier": r[6],
                "subscription_expires": r[7],
                "pref_gender": "ANY",
                "pref_country": "ANY",
                "partner_id": None,
                "blocked_users": {},
                "votes": {"up": r[8], "down": r[9]},
                "reports": r[10],
                "report_log": rep_log,
            }
    except Exception as e:
        logger.warning(f"_get_legacy_user error: {e}")
    return None


async def _load_legacy_user_data(conn) -> dict:
    data = {}
    try:
        tbl = await _get_legacy_table_name(conn)
        if not tbl:
            return {}
        cur = await conn.execute(f"""
            SELECT user_id, gender, age, country, preferences, points,
                   COALESCE(vote_up, 0) as vote_up,
                   COALESCE(vote_down, 0) as vote_down,
                   COALESCE(reports, 0) as reports,
                   report_log
            FROM {tbl};
        """)
        rows = await cur.fetchall()
        for r in rows:
            uid = r[0]
            rep_log = r[9]
            if isinstance(rep_log, str):
                try:
                    rep_log = json.loads(rep_log)
                except Exception:
                    rep_log = []
            elif not isinstance(rep_log, list):
                rep_log = []

            data[uid] = {
                "gender": r[1],
                "age": r[2],
                "country": r[3],
                "preferences": r[4] or 0,
                "points": r[5] or 0,
                "pref_gender": "ANY",
                "pref_country": "ANY",
                "partner_id": None,
                "blocked_users": {},
                "votes": {"up": r[6], "down": r[7]},
                "reports": r[8],
                "report_log": rep_log,
            }
        logger.info(f"Loaded {len(data)} legacy user records from {tbl} as fallback.")
    except Exception as e:
        logger.warning(f"_load_legacy_user_data error: {e}")
    return data


async def load_user_data() -> dict:
    """
    Backward-compatible load routine.
    Loads active users into memory with automatic fallback to legacy tables.
    """
    if not is_pool_ready():
        return {}
    p = get_pool()
    data = {}
    try:
        async with p.connection() as conn:
            cur = await conn.execute("SELECT (to_regclass('users') IS NOT NULL);")
            users_tbl_exists = (await cur.fetchone())[0]

            if users_tbl_exists:
                cur = await conn.execute("SELECT COUNT(*) FROM users;")
                users_count = (await cur.fetchone())[0]
            else:
                users_count = 0

            if users_count > 0:
                query = """
                    SELECT u.user_id, u.gender, u.age, u.country, u.preferences_bitmask as preferences, u.points,
                           COALESCE(p.preferred_gender, 'ANY') as pref_gender,
                           COALESCE(p.preferred_country, 'ANY') as pref_country,
                           GREATEST(COALESCE(p.votes_up, 0), COALESCE(r_up.votes_up, 0)) as votes_up,
                           GREATEST(COALESCE(p.votes_down, 0), COALESCE(r_down.votes_down, 0)) as votes_down,
                           GREATEST(COALESCE(p.reports_count, 0), COALESCE(rep.reports_count, 0)) as reports_count,
                           COALESCE(p.report_log, '[]'::jsonb) as report_log
                    FROM users u
                    LEFT JOIN user_profiles p ON u.user_id = p.user_id
                    LEFT JOIN (
                        SELECT target_id, COUNT(*) as votes_up 
                        FROM user_ratings WHERE vote_type = 'up' GROUP BY target_id
                    ) r_up ON u.user_id = r_up.target_id
                    LEFT JOIN (
                        SELECT target_id, COUNT(*) as votes_down 
                        FROM user_ratings WHERE vote_type = 'down' GROUP BY target_id
                    ) r_down ON u.user_id = r_down.target_id
                    LEFT JOIN (
                        SELECT target_id, COUNT(*) as reports_count 
                        FROM user_reports GROUP BY target_id
                    ) rep ON u.user_id = rep.target_id
                    ORDER BY u.updated_at DESC
                    LIMIT 50000;
                """
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(query)
                    rows = await cur.fetchall()
                    for r in rows:
                        uid = r["user_id"]
                        rep_log = r.get("report_log")
                        if isinstance(rep_log, str):
                            try:
                                rep_log = json.loads(rep_log)
                            except Exception:
                                rep_log = []
                        elif not isinstance(rep_log, list):
                            rep_log = []

                        data[uid] = {
                            "gender": r["gender"],
                            "age": r["age"],
                            "country": r["country"],
                            "preferences": r["preferences"] or 0,
                            "points": r["points"] or 0,
                            "pref_gender": r.get("pref_gender", "ANY"),
                            "pref_country": r.get("pref_country", "ANY"),
                            "partner_id": None,
                            "blocked_users": {},
                            "votes": {"up": r.get("votes_up", 0), "down": r.get("votes_down", 0)},
                            "reports": r.get("reports_count", 0),
                            "report_log": rep_log,
                        }
            else:
                data = await _load_legacy_user_data(conn)
    except Exception as e:
        logger.warning(f"Failed to load user data from database: {e}")
    return data
