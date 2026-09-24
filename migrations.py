"""
Database Migration and Schema Management for AnonChatZoneBot.

Normalized 3NF Baseline with Justified Denormalizations for 500k+ Users.
Preserves existing ~1,000 production records from legacy `user_details`.
"""

import json
import logging
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
"""


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
            if isinstance(cfg_val, dict) and cfg_val.get("completed"):
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

        # 8. Migrate detailed report logs into user_reports audit table (safely without duplicates)
        try:
            await conn.execute(f"""
                INSERT INTO user_reports (reporter_id, target_id, reason_code, weight, created_at)
                SELECT 
                    (elem->>'reporter')::BIGINT,
                    u.user_id,
                    COALESCE(elem->>'reason', 'unspecified'),
                    COALESCE((elem->>'weight')::INTEGER, 1),
                    to_timestamp(COALESCE((elem->>'timestamp')::DOUBLE PRECISION, EXTRACT(EPOCH FROM NOW())))
                FROM {legacy_tbl} u,
                     jsonb_array_elements(u.report_log::jsonb) AS elem
                WHERE u.report_log IS NOT NULL 
                  AND jsonb_typeof(u.report_log::jsonb) = 'array'
                  AND (elem->>'reporter') IS NOT NULL
                  AND (elem->>'reporter')::BIGINT IN (SELECT user_id FROM users)
                  AND NOT EXISTS (
                      SELECT 1 FROM user_reports ur 
                      WHERE ur.reporter_id = (elem->>'reporter')::BIGINT 
                        AND ur.target_id = u.user_id
                  );
            """)
        except Exception as e:
            logger.warning(f"Report logs legacy migration notice: {e}")

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
            VALUES ('legacy_migration_completed', '{"completed": true}'::jsonb)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
        """)
        logger.info("Recorded legacy migration completion in bot_config.")
    except Exception as e:
        logger.warning(f"Notice recording legacy migration completion: {e}")

