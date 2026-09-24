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



