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
