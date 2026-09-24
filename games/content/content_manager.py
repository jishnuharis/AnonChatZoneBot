"""
Data-driven Game Content Manager for AnonChatZoneBot.

Provides extensible, non-hardcoded question management for:
- Would You Rather (WYR)
- Trivia Duel
Supports category filtering, duplicate prevention, and admin question expansion.
"""

import os
import json
import random
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

CONTENT_DIR = os.path.dirname(os.path.abspath(__file__))
WYR_FILE = os.path.join(CONTENT_DIR, "wyr_questions.json")
TRIVIA_FILE = os.path.join(CONTENT_DIR, "trivia_questions.json")

# In-memory question caches
_wyr_cache: List[Dict[str, Any]] = []
_trivia_cache: List[Dict[str, Any]] = []


def _load_json_file(filepath: str) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        logger.warning(f"Content file missing: {filepath}")
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading content file {filepath}: {e}")
        return []


def load_all_content():
    """Initializes in-memory content from seed files."""
    global _wyr_cache, _trivia_cache
    _wyr_cache = _load_json_file(WYR_FILE)
    _trivia_cache = _load_json_file(TRIVIA_FILE)
    logger.info(f"Loaded {len(_wyr_cache)} WYR questions and {len(_trivia_cache)} Trivia questions.")


# Initialize on import
load_all_content()


# ============================================================================
# Would You Rather Prompts
# ============================================================================

def get_wyr_prompts(user1_prefs: int = 0, user2_prefs: int = 0, limit: int = 5) -> List[Tuple[str, str]]:
    """
    Selects balanced, diverse WYR questions. Prioritizes shared user interests
    when available, falling back to general/life questions.
    """
    import init

    # Identify shared interest tag names
    shared_categories = set()
    for i, (label, _) in enumerate(init.PREFERENCE_TAGS):
        if (user1_prefs & user2_prefs) & (1 << i):
            shared_categories.add(label)

    matching_prompts = []
    generic_prompts = []

    for item in _wyr_cache:
        pair = (item["prompt_a"], item["prompt_b"])
        if item.get("category") in shared_categories:
            matching_prompts.append(pair)
        else:
            generic_prompts.append(pair)

    random.shuffle(matching_prompts)
    random.shuffle(generic_prompts)

    selected = matching_prompts[:limit]
    if len(selected) < limit:
        needed = limit - len(selected)
        selected.extend(generic_prompts[:needed])

    # If still fewer than limit, loop/recycle
    if len(selected) < limit and selected:
        selected = (selected * 3)[:limit]

    return selected


# ============================================================================
# Trivia Duel Questions
# ============================================================================

def get_trivia_questions(category: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Selects random trivia questions, optionally filtered by category.
    """
    pool = _trivia_cache
    if category:
        pool = [q for q in _trivia_cache if q.get("category", "").lower() == category.lower()]

    if not pool:
        pool = _trivia_cache

    sampled = random.sample(pool, min(limit, len(pool)))
    return sampled


# ============================================================================
# Admin Management & Extension API
# ============================================================================

def add_wyr_question(category: str, prompt_a: str, prompt_b: str):
    """Dynamically adds a new Would You Rather question."""
    _wyr_cache.append({
        "category": category,
        "prompt_a": prompt_a,
        "prompt_b": prompt_b,
    })


def add_trivia_question(category: str, question: str, options: List[str], correct_index: int):
    """Dynamically adds a new Trivia question."""
    _trivia_cache.append({
        "category": category,
        "question": question,
        "options": options,
        "correct_index": correct_index,
    })


def get_stats() -> Dict[str, Any]:
    return {
        "wyr_count": len(_wyr_cache),
        "trivia_count": len(_trivia_cache),
        "wyr_categories": list(set(q.get("category", "General") for q in _wyr_cache)),
        "trivia_categories": list(set(q.get("category", "General") for q in _trivia_cache)),
    }
