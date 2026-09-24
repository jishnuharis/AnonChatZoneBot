"""
Automated Database Schema, 3NF Baseline & Migration Verification Tests.
"""

import pytest
from migrations import CREATE_TABLES_SQL


def test_schema_ddl_syntax():
    """Verify DDL contains all required 3NF tables, constraints, and indexes."""
    required_tables = [
        "CREATE TABLE IF NOT EXISTS users",
        "CREATE TABLE IF NOT EXISTS user_profiles",
        "CREATE TABLE IF NOT EXISTS user_blocks",
        "CREATE TABLE IF NOT EXISTS user_reports",
        "CREATE TABLE IF NOT EXISTS user_ratings",
        "CREATE TABLE IF NOT EXISTS chat_sessions",
        "CREATE TABLE IF NOT EXISTS subscriptions",
        "CREATE TABLE IF NOT EXISTS payment_transactions",
        "CREATE TABLE IF NOT EXISTS referrals",
        "CREATE TABLE IF NOT EXISTS bot_config",
        "CREATE TABLE IF NOT EXISTS promotions",
        "CREATE TABLE IF NOT EXISTS game_questions",
    ]
    for table_clause in required_tables:
        assert table_clause in CREATE_TABLES_SQL, f"Missing table DDL: {table_clause}"

    # Verify key constraints and indexes
    assert "CONSTRAINT uq_user_blocks UNIQUE (blocker_id, blocked_id)" in CREATE_TABLES_SQL
    assert "CONSTRAINT uq_user_ratings UNIQUE (voter_id, target_id)" in CREATE_TABLES_SQL
    assert "idx_sessions_active" in CREATE_TABLES_SQL
    assert "idx_profiles_restricted" in CREATE_TABLES_SQL
    assert "idx_blocks_lookup" in CREATE_TABLES_SQL


def test_user_profiles_schema_normalized_no_obsolete_columns():
    """Verify user_profiles DDL does not contain votes, reports, or feedback_track."""
    import re
    match = re.search(r"CREATE TABLE IF NOT EXISTS user_profiles \((.*?)\);", CREATE_TABLES_SQL, re.DOTALL)
    assert match is not None
    table_def = match.group(1)

    obsolete_columns = [
        "feedback_track", "partner_id", "voters", "points", "preferences",
        "subscription_expires", "subscription_tier", "referred_by", "referral_count",
        "votes_up", "votes_down", "reports_count", "report_log"
    ]
    for col in obsolete_columns:
        assert col not in table_def, f"Obsolete column '{col}' should not be in user_profiles schema DDL"



@pytest.mark.asyncio
async def test_check_user_profile_preserves_existing_user(monkeypatch):
    """
    Existing users in DB must NOT be prompted to re-register when check_user_profile runs.
    """
    from handlers.setup import check_user_profile
    from unittest.mock import AsyncMock, MagicMock
    import init

    user_id = 998877
    init.user_details.clear()

    # Mock get_user to simulate user already existing in PostgreSQL
    mock_db_user = {
        "user_id": user_id,
        "gender": "M",
        "age": 25,
        "country": "Germany",
        "preferences": 5,
        "points": 100,
        "pref_gender": "ANY",
        "pref_country": "ANY",
    }
    from saveNload import get_user
    monkeypatch.setattr("saveNload.get_user", AsyncMock(return_value=mock_db_user))

    target_handler_called = False
    @check_user_profile
    async def sample_handler(update, context):
        nonlocal target_handler_called
        target_handler_called = True

    mock_update = MagicMock()
    mock_update.effective_user.id = user_id
    mock_update.message.reply_text = AsyncMock()
    mock_context = MagicMock()

    await sample_handler(mock_update, mock_context)

    # Handler should execute directly without sending setup prompts
    assert target_handler_called is True
    assert mock_update.message.reply_text.call_count == 0
    assert init.user_details[user_id]["gender"] == "M"
    assert init.user_details[user_id]["age"] == 25
    assert init.user_details[user_id]["country"] == "Germany"


@pytest.mark.asyncio
async def test_legacy_user_votes_and_reports_structure(monkeypatch):
    """Verify legacy user extraction extracts votes, reports, and report_log."""
    from saveNload import _get_legacy_user
    from unittest.mock import AsyncMock, MagicMock
    import json

    mock_conn = MagicMock()
    # Mock _get_legacy_table_name to return 'legacy_user_details_backup'
    monkeypatch.setattr("saveNload._get_legacy_table_name", AsyncMock(return_value="legacy_user_details_backup"))

    mock_row = (
        12345, "F", 22, "Canada", 3, 50, "pro", 1700000000,
        15,  # vote_up
        2,   # vote_down
        4,   # reports
        json.dumps([{"reporter": 888, "reason": "spam", "weight": 1, "timestamp": 1690000000}])
    )

    mock_cur = MagicMock()
    mock_cur.fetchone = AsyncMock(return_value=mock_row)
    mock_conn.execute = AsyncMock(return_value=mock_cur)

    user = await _get_legacy_user(mock_conn, 12345)
    assert user is not None
    assert user["user_id"] == 12345
    assert user["gender"] == "F"
    assert user["votes"] == {"up": 15, "down": 2}
    assert user["reports"] == 4
    assert len(user["report_log"]) == 1
    assert user["report_log"][0]["reason"] == "spam"


def test_noisy_loggers_silenced():
    """Verify that APScheduler, httpx, and telegram loggers are configured to WARNING."""
    import logging
    import main  # Trigger logger level configurations

    for name in ("httpx", "httpcore", "apscheduler", "apscheduler.scheduler", "apscheduler.executors.default", "telegram"):
        assert logging.getLogger(name).level >= logging.WARNING


@pytest.mark.asyncio
async def test_database_heartbeat_ping(monkeypatch):
    """Verify ping_db issues SELECT 1 query to keep cloud database awake."""
    from saveNload import ping_db
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr("saveNload.is_pool_ready", lambda: True)

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockAsyncContextManager()
    monkeypatch.setattr("saveNload.get_pool", lambda: mock_pool)

    res = await ping_db()
    assert res is True
    mock_conn.execute.assert_awaited_once_with("SELECT 1;")


@pytest.mark.asyncio
async def test_save_user_data_triggers_heartbeat_when_idle(monkeypatch):
    """When dirty_user is empty, save_user_data should trigger ping_db heartbeat."""
    from saveNload import save_user_data
    from unittest.mock import AsyncMock

    mock_ping = AsyncMock(return_value=True)
    monkeypatch.setattr("saveNload.ping_db", mock_ping)

    await save_user_data({}, set())
    mock_ping.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_user_votes_queries_db_and_fallback(monkeypatch):
    from saveNload import get_user_votes
    from unittest.mock import AsyncMock, MagicMock
    import init

    # 1. Fallback when pool is not ready
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)
    init.user_details[111] = {"votes": {"up": 5, "down": 2}}
    votes = await get_user_votes(111)
    assert votes == {"up": 5, "down": 2}

    # 2. When pool is ready, query DB
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: True)
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone = AsyncMock(return_value=(12, 3))
    mock_conn.execute = AsyncMock(return_value=mock_cur)

    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockAsyncContextManager()
    monkeypatch.setattr("saveNload.get_pool", lambda: mock_pool)

    db_votes = await get_user_votes(222)
    assert db_votes == {"up": 12, "down": 3}


@pytest.mark.asyncio
async def test_build_profile_text_wires_votes_accurately(monkeypatch):
    from commands.profile import _build_profile_text
    from unittest.mock import AsyncMock, MagicMock
    import init

    user_id = 555666
    init.user_details[user_id] = {
        "user_id": user_id,
        "gender": "F",
        "age": 24,
        "country": "Japan",
        "preferences": 0,
        "points": 50,
        "votes": {"up": 0, "down": 0},
    }

    # Mock get_user_votes to return 7 up and 1 down
    monkeypatch.setattr("commands.profile.get_user_votes", AsyncMock(return_value={"up": 7, "down": 1}))

    mock_context = MagicMock()
    mock_chat = MagicMock()
    mock_chat.full_name = "Sakura"
    mock_chat.username = "sakura_jp"
    mock_context.bot.get_chat = AsyncMock(return_value=mock_chat)

    text = await _build_profile_text(user_id, mock_context)
    assert text is not None
    assert "<b>Rating:</b> 7 👍 1 👎" in text
    assert init.user_details[user_id]["votes"] == {"up": 7, "down": 1}


@pytest.mark.asyncio
async def test_handle_vote_does_not_corrupt_target_user(monkeypatch):
    from handlers.rating import handle_vote
    from unittest.mock import AsyncMock, MagicMock
    import init

    voter_id = 100
    target_id = 200

    # Target user exists with full profile in DB
    target_profile = {
        "user_id": target_id,
        "gender": "M",
        "age": 28,
        "country": "Spain",
        "preferences": 2,
        "points": 40,
        "votes": {"up": 4, "down": 1},
    }
    init.user_details.clear()
    init.dirty_users.clear()

    # Mock get_user so ensure_user_loaded restores their full profile
    monkeypatch.setattr("saveNload.get_user", AsyncMock(return_value=dict(target_profile)))
    monkeypatch.setattr("handlers.rating.record_user_rating", AsyncMock(return_value=True))
    monkeypatch.setattr("handlers.rating.get_user_votes", AsyncMock(return_value={"up": 5, "down": 1}))

    mock_update = MagicMock()
    mock_update.effective_user.id = voter_id
    mock_query = MagicMock()
    mock_query.data = f"rate|{target_id}|up"
    mock_query.answer = AsyncMock()
    mock_query.edit_message_reply_markup = AsyncMock()
    mock_update.callback_query = mock_query

    await handle_vote(mock_update, MagicMock())

    # Target user must preserve gender, age, country, and have updated votes
    assert target_id in init.user_details
    assert init.user_details[target_id]["gender"] == "M"
    assert init.user_details[target_id]["age"] == 28
    assert init.user_details[target_id]["country"] == "Spain"
    assert init.user_details[target_id]["votes"] == {"up": 5, "down": 1}
    # Target user shouldn't be added to dirty_users just from a rating
    assert target_id not in init.dirty_users


@pytest.mark.asyncio
async def test_add_subscription_db_uses_timedelta(monkeypatch):
    from saveNload import add_subscription_db
    from unittest.mock import AsyncMock, MagicMock
    from datetime import datetime, timezone

    monkeypatch.setattr("saveNload.is_pool_ready", lambda: True)

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_cur.fetchone = AsyncMock(return_value=None)
    mock_conn.execute = AsyncMock(return_value=mock_cur)

    class MockAsyncContextManager:
        async def __aenter__(self):
            return mock_conn
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    mock_pool = MagicMock()
    mock_pool.connection.return_value = MockAsyncContextManager()
    mock_conn.transaction.return_value = MockAsyncContextManager()
    monkeypatch.setattr("saveNload.get_pool", lambda: mock_pool)

    expiry = await add_subscription_db(777, "weekly", 7, source="purchase")
    assert isinstance(expiry, datetime)
    assert expiry > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_check_user_profile_country_stage_signature(monkeypatch):
    """Verify that when stage is 'country', send_country_selection is invoked with (user_id, context)."""
    from handlers.setup import check_user_profile
    from unittest.mock import AsyncMock, MagicMock
    import init

    user_id = 888999
    init.user_details[user_id] = {
        "user_id": user_id,
        "gender": "M",
        "age": None,
        "country": None,
    }
    init.user_input_stage[user_id] = "country"

    mock_send_country = AsyncMock()
    monkeypatch.setattr("handlers.country.send_country_selection", mock_send_country)

    mock_update = MagicMock()
    mock_update.effective_user.id = user_id
    mock_context = MagicMock()

    @check_user_profile
    async def dummy_handler(u, c):
        pass

    await dummy_handler(mock_update, mock_context)
    mock_send_country.assert_awaited_once_with(user_id, mock_context)


def test_parse_id_list_formats():
    """Verify _parse_id_list parses diverse PostgreSQL and JSON representations cleanly."""
    from migrations import _parse_id_list

    assert _parse_id_list(None) == []
    assert _parse_id_list("") == []
    assert _parse_id_list("[]") == []
    assert _parse_id_list("{}") == []
    assert _parse_id_list([111, 222, 333]) == [111, 222, 333]
    assert _parse_id_list(["111", "222"]) == [111, 222]
    assert _parse_id_list("[123, 456, 789]") == [123, 456, 789]
    assert _parse_id_list("{123, 456, 789}") == [123, 456, 789]
    assert _parse_id_list("{123,456}") == [123, 456]


@pytest.mark.asyncio
async def test_migrate_ratings_and_reports():
    """Verify _migrate_ratings_and_reports inserts into users, user_ratings, and user_reports."""
    from migrations import _migrate_ratings_and_reports
    from unittest.mock import AsyncMock, MagicMock
    import json

    executed_queries = []

    mock_conn = MagicMock()

    async def mock_execute(query, params=None):
        executed_queries.append((query, params))
        cur = MagicMock()
        if "information_schema.columns" in query:
            cur.fetchall = AsyncMock(return_value=[
                ("user_id",), ("vote_up",), ("vote_down",), ("voters",),
                ("reports",), ("reporters",), ("report_log",)
            ])
        elif "SELECT" in query and "FROM legacy_user_details_backup" in query:
            cur.fetchall = AsyncMock(return_value=[
                (
                    555, # user_id
                    2,   # vote_up
                    1,   # vote_down
                    "[101]", # voters (1 real voter for 3 total votes -> 2 synthetic needed)
                    2,   # reports
                    "[201]", # reporters
                    json.dumps([{"reporter": 301, "reason": "harassment", "weight": 2, "timestamp": 1700000000}])
                )
            ])
        else:
            cur.fetchall = AsyncMock(return_value=[])
            cur.fetchone = AsyncMock(return_value=None)
        return cur

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    await _migrate_ratings_and_reports(mock_conn, "legacy_user_details_backup")

    # Verify user foreign keys ensured
    users_insert = [q for q, p in executed_queries if "INSERT INTO users" in q]
    assert len(users_insert) > 0, "Must insert users to ensure foreign keys"

    # Verify user_ratings inserted
    ratings_insert = [q for q, p in executed_queries if "INSERT INTO user_ratings" in q]
    assert len(ratings_insert) > 0, "Must insert into user_ratings"

    # Verify user_reports inserted
    reports_insert = [q for q, p in executed_queries if "INSERT INTO user_reports" in q]
    assert len(reports_insert) > 0, "Must insert into user_reports"


@pytest.mark.asyncio
async def test_run_migrations_checks_ratings_migrated():
    """Verify run_migrations continues if legacy_migration_completed lacks ratings_migrated."""
    from migrations import run_migrations
    from unittest.mock import AsyncMock, MagicMock
    import json

    executed_queries = []
    mock_conn = MagicMock()

    async def mock_execute(query, params=None):
        executed_queries.append((query, params))
        cur = MagicMock()
        if "WHERE key = 'legacy_migration_completed'" in query:
            # Simulated partial run: completed: true, but ratings_migrated is missing
            cur.fetchone = AsyncMock(return_value=(json.dumps({"completed": True}),))
        elif "to_regclass" in query:
            cur.fetchone = AsyncMock(return_value=(False,))
        elif "information_schema.columns" in query:
            cur.fetchall = AsyncMock(return_value=[])
        else:
            cur.fetchall = AsyncMock(return_value=[])
            cur.fetchone = AsyncMock(return_value=(0,))
        return cur

    mock_conn.execute = AsyncMock(side_effect=mock_execute)

    await run_migrations(mock_conn)

    # Since ratings_migrated was not True, it should NOT have returned early at step 2
    # It must have checked for legacy tables
    legacy_checks = [q for q, p in executed_queries if "to_regclass" in q]
    assert len(legacy_checks) > 0, "Should inspect legacy tables when ratings_migrated is absent"





