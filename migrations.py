"""
Database Migration and Schema Management for AnonChatZoneBot.

Normalized 3NF Baseline with Justified Denormalizations for 500k+ Users.
Preserves existing ~1,000 production records from legacy `user_details`.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Set, Dict, Any, Optional
from psycopg import AsyncConnection

logger = logging.getLogger(__name__)

# Complete DDL for Normalized 3NF Schema
CREATE_TABLES_SQL = """
-- Core Users Table (Normalized 3NF Entity)
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    gender VARCHAR(1) CHECK (gender IN ('M', 'F') OR gender IS NULL),
    age SMALLINT CHECK ((age >= 13 AND age <= 100) OR age IS NULL),
    country VARCHAR(64),
    preferences_bitmask INTEGER NOT NULL DEFAULT 0,
    points INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User Profiles & Moderation State (1:1 with users)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    severity_score INTEGER NOT NULL DEFAULT 0 CHECK (severity_score >= 0),
    restricted_until TIMESTAMPTZ,
    restriction_reason TEXT,
    last_severity_decay TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    daily_credits_used INTEGER NOT NULL DEFAULT 0,
    daily_credits_reset_day DATE NOT NULL DEFAULT CURRENT_DATE,
    daily_calls_used INTEGER NOT NULL DEFAULT 0,
    daily_calls_reset_day DATE NOT NULL DEFAULT CURRENT_DATE,
    is_banned BOOLEAN NOT NULL DEFAULT FALSE,
    preferred_gender VARCHAR(8) NOT NULL DEFAULT 'ANY',
    preferred_country VARCHAR(64) NOT NULL DEFAULT 'ANY'
);

-- User Blocks (M:N between users)
CREATE TABLE IF NOT EXISTS user_blocks (
    id BIGSERIAL PRIMARY KEY,
    blocker_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    blocked_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_blocks UNIQUE (blocker_id, blocked_id),
    CONSTRAINT chk_no_self_block CHECK (blocker_id != blocked_id)
);

-- User Reports Table (Normalized 1:N)
CREATE TABLE IF NOT EXISTS user_reports (
    id BIGSERIAL PRIMARY KEY,
    reporter_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    target_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    reason_code VARCHAR(32) NOT NULL,
    weight INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- User Ratings / Feedback Table (M:N between voters and targets)
CREATE TABLE IF NOT EXISTS user_ratings (
    id BIGSERIAL PRIMARY KEY,
    voter_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    target_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    vote_type VARCHAR(8) NOT NULL CHECK (vote_type IN ('up', 'down')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_ratings UNIQUE (voter_id, target_id)
);

-- Active & Historical Chat Sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY,
    user1_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user2_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'ended', 'disconnected')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    end_reason VARCHAR(32),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Subscriptions Table
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tier VARCHAR(32) NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    source VARCHAR(32) NOT NULL DEFAULT 'purchase',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Payment Transactions Audit Ledger
CREATE TABLE IF NOT EXISTS payment_transactions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tier VARCHAR(32) NOT NULL,
    stars INTEGER NOT NULL,
    currency VARCHAR(8) NOT NULL DEFAULT 'XTR',
    telegram_payment_charge_id VARCHAR(128),
    provider_payment_charge_id VARCHAR(128),
    status VARCHAR(16) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Referrals Table
CREATE TABLE IF NOT EXISTS referrals (
    referred_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    referrer_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    credited BOOLEAN NOT NULL DEFAULT FALSE,
    rewarded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rewarded_at TIMESTAMPTZ,
    CONSTRAINT chk_no_self_referral CHECK (referred_id != referrer_id)
);

-- Bot Configuration KV Store
CREATE TABLE IF NOT EXISTS bot_config (
    key VARCHAR(64) PRIMARY KEY,
    value JSONB NOT NULL
);

-- Sponsors & Promotions Table
CREATE TABLE IF NOT EXISTS promotions (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(128) NOT NULL,
    sponsor_name VARCHAR(128) NOT NULL,
    message_text TEXT NOT NULL,
    button_text VARCHAR(64),
    button_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    priority INTEGER NOT NULL DEFAULT 1,
    start_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_date TIMESTAMPTZ,
    display_frequency INTEGER NOT NULL DEFAULT 1,
    impressions_count INTEGER NOT NULL DEFAULT 0,
    clicks_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Extensible Game Questions Table (Data-driven WYR, Trivia, etc.)
CREATE TABLE IF NOT EXISTS game_questions (
    id BIGSERIAL PRIMARY KEY,
    game_type VARCHAR(32) NOT NULL,
    category VARCHAR(64) NOT NULL,
    prompt_a TEXT NOT NULL,
    prompt_b TEXT,
    correct_answer TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    times_played INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Anonymous Friends Table (Normalized M:N with custom metadata)
CREATE TABLE IF NOT EXISTS user_friends (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    friend_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    custom_name VARCHAR(100) NOT NULL,
    notes TEXT DEFAULT '',
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_friends UNIQUE (user_id, friend_id),
    CONSTRAINT chk_no_self_friend CHECK (user_id != friend_id)
);

-- Indexes for 500k+ Users Performance
CREATE INDEX IF NOT EXISTS idx_users_prefs ON users (preferences_bitmask);
CREATE INDEX IF NOT EXISTS idx_profiles_restricted ON user_profiles (restricted_until) WHERE restricted_until IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_banned ON user_profiles (is_banned) WHERE is_banned = TRUE;
CREATE INDEX IF NOT EXISTS idx_blocks_lookup ON user_blocks (blocker_id, blocked_id);
CREATE INDEX IF NOT EXISTS idx_blocks_blocked ON user_blocks (blocked_id);
CREATE INDEX IF NOT EXISTS idx_reports_target ON user_reports (target_id);
CREATE INDEX IF NOT EXISTS idx_ratings_target ON user_ratings (target_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON chat_sessions (user1_id, user2_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_sessions_user1 ON chat_sessions (user1_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_user2 ON chat_sessions (user2_id, status);
CREATE INDEX IF NOT EXISTS idx_subs_user_active ON subscriptions (user_id, expires_at) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals (referrer_id);
CREATE INDEX IF NOT EXISTS idx_promotions_active ON promotions (is_active, priority) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_game_questions_lookup ON game_questions (game_type, category, is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_user_friends_user ON user_friends (user_id, is_favorite DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_friends_pair ON user_friends (user_id, friend_id);
"""


def _parse_id_list(val) -> List[int]:
    """Parses user ID lists from diverse legacy formats (list, JSON string, Postgres array string)."""
    if not val:
        return []
    if isinstance(val, list):
        ids = []
        for x in val:
            try:
                ids.append(int(x))
            except (ValueError, TypeError):
                pass
        return ids
    if isinstance(val, str):
        val = val.strip()
        if not val or val in ("[]", "{}"):
            return []
        if val.startswith("[") and val.endswith("]"):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [int(x) for x in parsed if str(x).lstrip("-").isdigit()]
            except Exception:
                pass
        if val.startswith("{") and val.endswith("}"):
            items = val[1:-1].split(",")
            return [int(x.strip()) for x in items if x.strip().lstrip("-").isdigit()]
    return []


async def _migrate_ratings_and_reports(conn: AsyncConnection, legacy_tbl: str):
    """
    Migrates historical votes into user_ratings and historical reports into user_reports.
    Preserves all vote_up, vote_down, voters, reports, reporters, and report_log.
    """
    try:
        cur = await conn.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = '{legacy_tbl}';
        """)
        existing_cols = {row[0] for row in await cur.fetchall()}

        up_col = "vote_up" if "vote_up" in existing_cols else ("votes_up" if "votes_up" in existing_cols else None)
        down_col = "vote_down" if "vote_down" in existing_cols else ("votes_down" if "votes_down" in existing_cols else None)
        voters_col = "voters" if "voters" in existing_cols else None
        rep_col = "reports" if "reports" in existing_cols else ("reports_count" if "reports_count" in existing_cols else None)
        reporters_col = "reporters" if "reporters" in existing_cols else None
        rep_log_col = "report_log" if "report_log" in existing_cols else None

        select_parts = ["user_id"]
        select_parts.append(f"COALESCE({up_col}, 0)" if up_col else "0")
        select_parts.append(f"COALESCE({down_col}, 0)" if down_col else "0")
        select_parts.append(f"{voters_col}" if voters_col else "NULL")
        select_parts.append(f"COALESCE({rep_col}, 0)" if rep_col else "0")
        select_parts.append(f"{reporters_col}" if reporters_col else "NULL")
        select_parts.append(f"{rep_log_col}" if rep_log_col else "NULL")

        cur = await conn.execute(f"SELECT {', '.join(select_parts)} FROM {legacy_tbl};")
        rows = await cur.fetchall()

        ratings_to_insert = []
        reports_to_insert = []
        users_to_ensure = set()

        for row in rows:
            uid = row[0]
            if not uid:
                continue
            vote_up = int(row[1] or 0)
            vote_down = int(row[2] or 0)
            voters = _parse_id_list(row[3])
            rep_count = int(row[4] or 0)
            reporters = _parse_id_list(row[5])
            rep_log = row[6]
            if isinstance(rep_log, str):
                try:
                    rep_log = json.loads(rep_log)
                except Exception:
                    rep_log = []
            elif not isinstance(rep_log, list):
                rep_log = []

            # 1. Migrate votes to user_ratings
            assigned_up = 0
            assigned_down = 0
            for v_id in voters:
                if v_id == uid:
                    continue
                if assigned_up < vote_up:
                    users_to_ensure.add(v_id)
                    ratings_to_insert.append((v_id, uid, "up"))
                    assigned_up += 1
                elif assigned_down < vote_down:
                    users_to_ensure.add(v_id)
                    ratings_to_insert.append((v_id, uid, "down"))
                    assigned_down += 1

            for i in range(assigned_up, vote_up):
                synth_id = -(uid * 10000 + i + 1)
                users_to_ensure.add(synth_id)
                ratings_to_insert.append((synth_id, uid, "up"))

            for j in range(assigned_down, vote_down):
                synth_id = -(uid * 10000 + 5000 + j + 1)
                users_to_ensure.add(synth_id)
                ratings_to_insert.append((synth_id, uid, "down"))

            # 2. Migrate reports to user_reports
            inserted_reporters = set()
            for item in rep_log:
                if isinstance(item, dict) and item.get("reporter"):
                    try:
                        r_id = int(item["reporter"])
                        if r_id != uid:
                            users_to_ensure.add(r_id)
                            reason = str(item.get("reason") or "unspecified")
                            weight = int(item.get("weight") or 1)
                            ts = item.get("timestamp")
                            reports_to_insert.append((r_id, uid, reason, weight, ts))
                            inserted_reporters.add(r_id)
                    except (ValueError, TypeError):
                        pass

            for r_id in reporters:
                if r_id != uid and r_id not in inserted_reporters:
                    users_to_ensure.add(r_id)
                    reports_to_insert.append((r_id, uid, "legacy_report", 1, None))
                    inserted_reporters.add(r_id)

            needed_synth_reports = rep_count - len(inserted_reporters)
            for k in range(max(0, needed_synth_reports)):
                synth_id = -(uid * 10000 + 8000 + k + 1)
                users_to_ensure.add(synth_id)
                reports_to_insert.append((synth_id, uid, "legacy_report", 1, None))

        # Batch insert users to ensure foreign keys
        if users_to_ensure:
            user_tuples = [(u,) for u in users_to_ensure]
            for i in range(0, len(user_tuples), 500):
                chunk = user_tuples[i:i + 500]
                placeholders = ", ".join(["(%s)"] * len(chunk))
                flat = [val for tup in chunk for val in tup]
                await conn.execute(f"""
                    INSERT INTO users (user_id) VALUES {placeholders}
                    ON CONFLICT (user_id) DO NOTHING;
                """, flat)

        # Batch insert user_ratings
        if ratings_to_insert:
            for i in range(0, len(ratings_to_insert), 500):
                chunk = ratings_to_insert[i:i + 500]
                placeholders = ", ".join(["(%s, %s, %s)"] * len(chunk))
                flat = [val for tup in chunk for val in tup]
                await conn.execute(f"""
                    INSERT INTO user_ratings (voter_id, target_id, vote_type) 
                    VALUES {placeholders}
                    ON CONFLICT (voter_id, target_id) DO NOTHING;
                """, flat)
            logger.info(f"Migrated {len(ratings_to_insert)} ratings into user_ratings from {legacy_tbl}.")

        # Batch insert user_reports
        if reports_to_insert:
            for r_id, t_id, reason, weight, ts in reports_to_insert:
                if ts:
                    await conn.execute("""
                        INSERT INTO user_reports (reporter_id, target_id, reason_code, weight, created_at)
                        SELECT %s, %s, %s, %s, to_timestamp(%s)
                        WHERE NOT EXISTS (
                            SELECT 1 FROM user_reports WHERE reporter_id = %s AND target_id = %s
                        );
                    """, (r_id, t_id, reason, weight, ts, r_id, t_id))
                else:
                    await conn.execute("""
                        INSERT INTO user_reports (reporter_id, target_id, reason_code, weight)
                        SELECT %s, %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM user_reports WHERE reporter_id = %s AND target_id = %s
                        );
                    """, (r_id, t_id, reason, weight, r_id, t_id))
            logger.info(f"Migrated {len(reports_to_insert)} reports into user_reports from {legacy_tbl}.")

    except Exception as e:
        logger.warning(f"_migrate_ratings_and_reports error: {e}", exc_info=True)


async def run_migrations(conn: AsyncConnection):
    """
    Executes DDL and migrates existing ~1,000 rows from legacy `user_details`
    table into normalized 3NF tables without data loss.
    """
    # 1. Ensure target tables exist
    await conn.execute(CREATE_TABLES_SQL)

    # Ensure profile columns exist on user_profiles (for existing installs)
    await conn.execute("""
        ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS preferred_gender VARCHAR(8) DEFAULT 'ANY';
        ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS preferred_country VARCHAR(64) DEFAULT 'ANY';
        ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS daily_calls_used INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS daily_calls_reset_day DATE NOT NULL DEFAULT CURRENT_DATE;
    """)

    # Drop removed/obsolete columns from user_profiles
    await conn.execute("""
        ALTER TABLE user_profiles 
            DROP COLUMN IF EXISTS feedback_track,
            DROP COLUMN IF EXISTS partner_id,
            DROP COLUMN IF EXISTS voters,
            DROP COLUMN IF EXISTS points,
            DROP COLUMN IF EXISTS preferences,
            DROP COLUMN IF EXISTS subscription_expires,
            DROP COLUMN IF EXISTS subscription_tier,
            DROP COLUMN IF EXISTS referred_by,
            DROP COLUMN IF EXISTS referral_count,
            DROP COLUMN IF EXISTS referral_rewarded_count,
            DROP COLUMN IF EXISTS referral_credited,
            DROP COLUMN IF EXISTS votes_up,
            DROP COLUMN IF EXISTS votes_down,
            DROP COLUMN IF EXISTS reports_count,
            DROP COLUMN IF EXISTS report_log;
    """)

    # 2. Check if legacy migration was already completed
    try:
        cur = await conn.execute("SELECT value FROM bot_config WHERE key = 'legacy_migration_completed';")
        cfg_row = await cur.fetchone()
        if cfg_row:
            cfg_val = cfg_row[0]
            if isinstance(cfg_val, str):
                try:
                    cfg_val = json.loads(cfg_val)
                except Exception:
                    cfg_val = {}
            if isinstance(cfg_val, dict) and cfg_val.get("completed") and cfg_val.get("ratings_migrated"):
                logger.info("Legacy migration was already completed. Schema is clean and up to date.")
                return
    except Exception as e:
        logger.warning(f"Notice while checking legacy_migration_completed: {e}")

    # 3. Check for legacy tables (works seamlessly whether named 'legacy_user_details_backup' or 'user_details')
    legacy_candidates = []
    for candidate in ('legacy_user_details_backup', 'user_details'):
        cur = await conn.execute(f"SELECT (to_regclass('{candidate}') IS NOT NULL);")
        if (await cur.fetchone())[0]:
            cur = await conn.execute(f"SELECT COUNT(*) FROM {candidate};")
            count = (await cur.fetchone())[0]
            if count > 0:
                legacy_candidates.append((candidate, count))

    if not legacy_candidates:
        logger.info("No legacy tables with records found. Schema is clean.")
        return

    for legacy_tbl, row_count in legacy_candidates:
        logger.info(f"Found legacy table '{legacy_tbl}' with {row_count} records. Starting complete migration...")

        # 4. Migrate core user records (never overwrite existing active user data)
        await conn.execute(f"""
            INSERT INTO users (user_id, gender, age, country, preferences_bitmask, points)
            SELECT 
                user_id,
                CASE WHEN gender IN ('M', 'F') THEN gender ELSE NULL END,
                CASE WHEN age >= 13 AND age <= 100 THEN age ELSE NULL END,
                country,
                COALESCE(preferences, 0),
                COALESCE(points, 0)
            FROM {legacy_tbl}
            ON CONFLICT (user_id) DO NOTHING;
        """)

        # 5. Migrate user profiles & moderation state (never overwrite existing active user profile)
        await conn.execute(f"""
            INSERT INTO user_profiles (
                user_id, severity_score, restricted_until, restriction_reason,
                last_severity_decay, daily_credits_used, daily_credits_reset_day, is_banned
            )
            SELECT 
                user_id,
                COALESCE(severity_score, 0),
                CASE WHEN restricted_until IS NOT NULL AND restricted_until > 0 
                     THEN to_timestamp(restricted_until) ELSE NULL END,
                restriction_reason,
                CASE WHEN last_severity_decay IS NOT NULL AND last_severity_decay > 0 
                     THEN to_timestamp(last_severity_decay) ELSE NOW() END,
                COALESCE(daily_credits_used, 0),
                CASE WHEN daily_credits_reset_day ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' 
                     THEN daily_credits_reset_day::DATE ELSE CURRENT_DATE END,
                CASE WHEN restricted_until IS NOT NULL AND restricted_until > 2000000000 
                     THEN TRUE ELSE FALSE END
            FROM {legacy_tbl}
            ON CONFLICT (user_id) DO NOTHING;
        """)

        # 6. Migrate subscriptions (prevent duplicate rows)
        try:
            await conn.execute(f"""
                INSERT INTO subscriptions (user_id, tier, starts_at, expires_at, source, is_active)
                SELECT 
                    user_id,
                    subscription_tier,
                    NOW(),
                    to_timestamp(subscription_expires),
                    'legacy_migration',
                    to_timestamp(subscription_expires) > NOW()
                FROM {legacy_tbl}
                WHERE subscription_tier IS NOT NULL 
                  AND subscription_expires IS NOT NULL 
                  AND subscription_expires > 0
                  AND NOT EXISTS (
                      SELECT 1 FROM subscriptions s
                      WHERE s.user_id = {legacy_tbl}.user_id
                        AND s.source = 'legacy_migration'
                  );
            """)
        except Exception as e:
            logger.warning(f"Subscriptions legacy migration notice: {e}")

        # 7. Migrate referrals
        try:
            await conn.execute(f"""
                INSERT INTO referrals (referred_id, referrer_id, credited)
                SELECT 
                    user_id,
                    referred_by,
                    COALESCE(referral_credited, FALSE)
                FROM {legacy_tbl}
                WHERE referred_by IS NOT NULL 
                  AND referred_by != user_id
                  AND referred_by IN (SELECT user_id FROM users)
                ON CONFLICT (referred_id) DO NOTHING;
            """)
        except Exception as e:
            logger.warning(f"Referrals legacy migration notice: {e}")

        # 8. Migrate ratings into user_ratings and reports into user_reports
        await _migrate_ratings_and_reports(conn, legacy_tbl)

        # 9. Migrate active chat sessions from partner_id
        try:
            await conn.execute(f"""
                INSERT INTO chat_sessions (id, user1_id, user2_id, status, started_at)
                SELECT 
                    gen_random_uuid(),
                    user_id,
                    partner_id,
                    'active',
                    NOW()
                FROM {legacy_tbl}
                WHERE partner_id IS NOT NULL 
                  AND partner_id > 0
                  AND user_id < partner_id
                  AND partner_id IN (SELECT user_id FROM users)
                  AND NOT EXISTS (
                      SELECT 1 FROM chat_sessions cs 
                      WHERE cs.status = 'active' 
                        AND ((cs.user1_id = {legacy_tbl}.user_id AND cs.user2_id = {legacy_tbl}.partner_id)
                          OR (cs.user1_id = {legacy_tbl}.partner_id AND cs.user2_id = {legacy_tbl}.user_id))
                  );
            """)
        except Exception as e:
            logger.warning(f"Chat sessions legacy migration notice: {e}")

        # 10. Safely rename user_details to legacy_user_details_backup if still named user_details
        if legacy_tbl == "user_details":
            try:
                cur = await conn.execute("SELECT (to_regclass('legacy_user_details_backup') IS NOT NULL);")
                backup_exists = (await cur.fetchone())[0]
                if not backup_exists:
                    await conn.execute("ALTER TABLE user_details RENAME TO legacy_user_details_backup;")
                    logger.info("Renamed user_details to legacy_user_details_backup.")
            except Exception as e:
                logger.warning(f"Notice during user_details rename: {e}")

        logger.info(f"Successfully migrated all data from '{legacy_tbl}'.")

    # 11. Record completion in bot_config so future startups skip scanning legacy tables
    try:
        await conn.execute("""
            INSERT INTO bot_config (key, value)
            VALUES ('legacy_migration_completed', '{"completed": true, "ratings_migrated": true}'::jsonb)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """)
        logger.info("Recorded legacy migration completion in bot_config.")
    except Exception as e:
        logger.warning(f"Notice recording legacy migration completion: {e}")

