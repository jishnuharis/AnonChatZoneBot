"""
Automated Games Framework, WYR Expansion & Trivia Duel Tests.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

import init
from games import registry
import games.would_you_rather as wyr
import games.trivia as trivia
from games.content.content_manager import get_wyr_prompts, get_trivia_questions


@pytest.fixture(autouse=True)
def reset_globals():
    registry.active_game_of.clear()
    wyr.games.clear()
    wyr.user_to_session.clear()
    trivia.games.clear()
    trivia.user_to_session.clear()
    init.user_details.clear()


def test_wyr_data_driven_prompts():
    """Verify Would You Rather retrieves rich prompts from content system."""
    prompts = get_wyr_prompts(user1_prefs=0b0011, user2_prefs=0b0011, limit=5)
    assert len(prompts) == 5
    for a, b in prompts:
        assert isinstance(a, str) and len(a) > 0
        assert isinstance(b, str) and len(b) > 0
        assert a != b


def test_trivia_questions_data_driven():
    """Verify Trivia questions have 4 options and valid correct index."""
    questions = get_trivia_questions(limit=5)
    assert len(questions) == 5
    for q in questions:
        assert "question" in q
        assert "options" in q
        assert len(q["options"]) == 4
        assert 0 <= q["correct_index"] <= 3


def test_trivia_expansion_and_option_shuffling():
    """Verify 10 categories with 128 questions each, option shuffling, and consistent emojis."""
    from games.content.content_manager import get_stats, _trivia_cache

    stats = get_stats()
    assert stats["trivia_count"] >= 1280
    assert len(stats["trivia_categories"]) == 10

    expected_categories = [
        "Science", "Geography", "History", "Gaming", "Movies & TV",
        "Anime & Manga", "Music", "Sports", "General Knowledge", "Riddles & Brain Teasers"
    ]
    for cat in expected_categories:
        cat_questions = [q for q in _trivia_cache if q.get("category") == cat]
        assert len(cat_questions) == 128, f"Category {cat} has {len(cat_questions)}, expected 128"

    # Test that options are shuffled dynamically and track the right answer
    orig_q = _trivia_cache[0]
    expected_answer = orig_q["options"][orig_q["correct_index"]]
    sampled = get_trivia_questions(limit=1)[0]
    assert sampled["options"][sampled["correct_index"]] in [q["options"][q["correct_index"]] for q in _trivia_cache]

    # Verify OPTION_LABELS consistency
    assert len(trivia.OPTION_LABELS) == 4
    for label in trivia.OPTION_LABELS:
        assert label.endswith("\ufe0e")


@pytest.mark.asyncio
async def test_trivia_session_creation_and_teardown():
    u1, u2 = 10, 20
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()

    session_id = trivia.create_session(u1, u2)
    assert session_id is not None
    assert registry.get_active(u1) == "trivia"
    assert registry.get_active(u2) == "trivia"

    # Partner forfeit
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock())

    await trivia.force_end_game(mock_context, u1)

    assert registry.get_active(u1) is None
    assert registry.get_active(u2) is None
    # Remaining player (u2) awarded forfeit points (+5)
    assert init.user_details[u2]["points"] == 5


@pytest.mark.asyncio
async def test_wyr_session_creation():
    u1, u2 = 30, 40
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()

    session_id = wyr.create_session(u1, u2)
    assert session_id is not None
    assert registry.get_active(u1) == "wyr"
    assert registry.get_active(u2) == "wyr"
    assert len(wyr.games[session_id]["prompts"]) == 5


def test_wyr_expansion_and_option_randomization():
    """Verify 8 WYR categories with 128 questions each, option randomization, and consistent labels."""
    from games.content.content_manager import get_stats, _wyr_cache

    stats = get_stats()
    assert stats["wyr_count"] >= 1024
    assert len(stats["wyr_categories"]) == 8

    expected_categories = [
        "Life & Superpowers", "Relationships", "Gaming", "Anime",
        "Movies & Pop Culture", "Philosophy & Deep Thoughts", "Tech & Future", "Memes & Absurd"
    ]
    for cat in expected_categories:
        cat_prompts = [q for q in _wyr_cache if q.get("category") == cat]
        assert len(cat_prompts) == 128, f"Category {cat} has {len(cat_prompts)}, expected 128"

    # Verify labels consistency
    assert wyr.LABEL_A.endswith("\ufe0e")
    assert wyr.LABEL_B.endswith("\ufe0e")

    # Verify prompts generation and randomization
    prompts = get_wyr_prompts(limit=10)
    assert len(prompts) == 10
    for a, b in prompts:
        assert isinstance(a, str) and len(a) > 0
        assert isinstance(b, str) and len(b) > 0
        assert a != b
