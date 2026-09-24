"""
Automated Moderation, Severity Scoring, Ban & Decay Tests.
"""

import pytest
import time
from unittest.mock import MagicMock, AsyncMock

import init
from moderation import (
    severity_for_score,
    apply_restriction,
    clear_restriction,
    file_report,
    is_user_restricted,
    is_admin,
    SEVERITY_DURATIONS,
)


@pytest.fixture(autouse=True)
def reset_globals():
    init.user_details.clear()
    init.waiting_users.clear()
    init.active_pairs.clear()
    init.dirty_users.clear()
    init.ADMIN_IDS.clear()
    init.OWNER = "99999"


@pytest.mark.asyncio
async def test_severity_thresholds():
    assert severity_for_score(0) == 0
    assert severity_for_score(31) == 0
    assert severity_for_score(32) == 1
    assert severity_for_score(48) == 2
    assert severity_for_score(105) == 5
    assert severity_for_score(200) == 10
    assert severity_for_score(500) == 10


@pytest.mark.asyncio
async def test_admin_cannot_be_restricted():
    admin_id = 99999 # OWNER
    mock_context = MagicMock()
    result = await apply_restriction(admin_id, severity=10, reason="Test", context=mock_context)
    assert result is None
    restricted, _, _ = is_user_restricted(admin_id)
    assert restricted is False


@pytest.mark.asyncio
async def test_apply_and_clear_restriction():
    target_id = 1234
    init.user_details[target_id] = init._default_user()
    mock_context = MagicMock()

    # Apply severity 2 restriction (30 mins)
    until = await apply_restriction(target_id, severity=2, reason="Rude behavior", context=mock_context)
    assert until is not None
    assert until > time.time()

    restricted, reason, remaining = is_user_restricted(target_id)
    assert restricted is True
    assert reason == "Rude behavior"
    assert remaining > 0

    # Clear restriction
    await clear_restriction(target_id)
    restricted, _, _ = is_user_restricted(target_id)
    assert restricted is False


@pytest.mark.asyncio
async def test_file_report_and_auto_escalation():
    reporter = 111
    target = 222
    init.user_details[reporter] = init._default_user()
    init.user_details[target] = init._default_user()
    mock_context = MagicMock()

    # Underage concern has weight 10
    weight, score, triggered = await file_report(reporter, target, "minor", context=mock_context)
    assert weight == 10
    assert score == 10
    assert triggered is None

    # Duplicate report from same reporter within 24 hours has 0 effective weight (anti-griefing)
    dup_weight, dup_score, _ = await file_report(reporter, target, "nsfw", context=mock_context)
    assert dup_weight == 0
    assert dup_score == 10

    # A different reporter reporting increases severity score
    reporter2 = 333
    init.user_details[reporter2] = init._default_user()
    init.user_details[target]["severity_score"] = 30
    weight, score, triggered = await file_report(reporter2, target, "nsfw", context=mock_context) # +4 -> 34
    assert weight == 4
    assert score == 34
    # Crosses threshold 32 -> Level 1 restriction triggered!
    assert triggered == 1

    restricted, _, _ = is_user_restricted(target)
    assert restricted is True
