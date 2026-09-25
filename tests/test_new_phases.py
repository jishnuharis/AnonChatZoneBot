"""
Comprehensive Unit & Integration Tests for:
1. Common Interest Reveal on Connect + Conversation Starters
2. Daily Chat Streaks & Extended Rewards Engine
3. Upgraded Weekly Leaderboard (/top)
4. Telegram Stars In-Chat Gifting (/gift)
"""

import time
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import init
from session_manager import start_chat_session, end_chat_session, is_in_chat, _build_shared_interest_or_icebreaker
from streaks import (
    update_streak_on_chat,
    claim_milestone_reward,
    get_next_streak_milestone,
    get_streak_info,
    STREAK_REWARDS,
)
from commands.top import (
    render_leaderboard_text,
    anonymize_id,
    show_top_leaderboard,
    handle_top_callback,
    fetch_leaderboard,
)
from commands.gift import gift_command, handle_gift_callback, GIFTS
from handlers.payments import handle_pre_checkout, handle_successful_payment


# ============================================================================
# 1. Common Interest Reveal on Connect & Conversation Starters
# ============================================================================

def test_anonymize_id():
    assert anonymize_id(628612345) == "6286***"
    assert anonymize_id(1234) == "1234***"
    assert anonymize_id(99) == "99***"


def test_shared_interest_reveal_matching_tags():
    u1, u2 = 1001, 1002
    # Bits 0: Gaming (1), 1: Anime (2) -> 3
    init.user_details[u1] = {**init._default_user(), "preferences": 3}
    init.user_details[u2] = {**init._default_user(), "preferences": 3}

    text = _build_shared_interest_or_icebreaker(u1, u2)
    assert "✨ <b>You both like:</b>" in text
    assert "Gaming" in text
    assert "Anime" in text


def test_shared_interest_reveal_icebreaker_fallback_when_no_match():
    u1, u2 = 1003, 1004
    # u1 likes Gaming (1), u2 likes Anime (2) -> overlap 0
    init.user_details[u1] = {**init._default_user(), "preferences": 1}
    init.user_details[u2] = {**init._default_user(), "preferences": 2}

    text = _build_shared_interest_or_icebreaker(u1, u2)
    assert "💡 <i>Icebreaker:</i>" in text
    assert "You both like" not in text


@pytest.mark.asyncio
async def test_start_chat_session_delivers_shared_interests_or_icebreaker(monkeypatch):
    monkeypatch.setattr("saveNload.is_blocked_pairwise", AsyncMock(return_value=False))
    monkeypatch.setattr("saveNload.create_chat_session_db", AsyncMock(return_value="test-uuid-interests"))

    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=123))

    u1, u2 = 2001, 2002
    # Both share Music (bit 3 = 8)
    init.user_details[u1] = {**init._default_user(), "preferences": 8}
    init.user_details[u2] = {**init._default_user(), "preferences": 8}

    ok = await start_chat_session(context, u1, u2)
    assert ok is True
    assert context.bot.send_message.call_count == 2

    # Check both received shared interest tag
    text1 = context.bot.send_message.call_args_list[0][1]["text"]
    text2 = context.bot.send_message.call_args_list[1][1]["text"]
    assert "Music" in text1
    assert "Music" in text2


# ============================================================================
# 2. Daily Chat Streaks & Extended Rewards Engine
# ============================================================================

def test_streak_progression_and_broken_reset():
    uid = 3001
    init.user_details[uid] = init._default_user()

    d1 = date(2026, 9, 20)
    d2 = date(2026, 9, 21)
    d3 = date(2026, 9, 22)
    d5 = date(2026, 9, 24)  # Skipped Sep 23!

    # Day 1
    st, inc, rew = update_streak_on_chat(uid, target_date=d1)
    assert st == 1
    assert inc is True
    assert rew is None

    # Day 1 again on same day
    st, inc, rew = update_streak_on_chat(uid, target_date=d1)
    assert st == 1
    assert inc is False

    # Day 2
    st, inc, rew = update_streak_on_chat(uid, target_date=d2)
    assert st == 2
    assert inc is True

    # Day 3 -> Unlocks milestone 3!
    st, inc, rew = update_streak_on_chat(uid, target_date=d3)
    assert st == 3
    assert inc is True
    assert rew is not None
    assert rew["type"] == "credits"
    assert rew["amount"] == 50

    # Missed a day -> Resets to 1, but longest_streak remains 3!
    st, inc, rew = update_streak_on_chat(uid, target_date=d5)
    assert st == 1
    assert inc is True
    info = get_streak_info(uid)
    assert info["longest_streak"] == 3


@pytest.mark.asyncio
async def test_streak_extended_milestones_and_rewards(monkeypatch):
    monkeypatch.setattr("saveNload.add_subscription_db", AsyncMock())

    uid = 3002
    init.user_details[uid] = {**init._default_user(), "points": 100}
    bot = MagicMock()
    bot.send_message = AsyncMock()

    # Milestone 3 (+50 credits)
    await claim_milestone_reward(bot, uid, 3, STREAK_REWARDS[3])
    assert init.user_details[uid]["points"] == 150
    assert 3 in init.user_details[uid]["streak_rewards_claimed"]
    assert bot.send_message.called

    # Milestone 7 (1 Day VIP)
    await claim_milestone_reward(bot, uid, 7, STREAK_REWARDS[7])
    assert init.user_details[uid]["subscription_expires"] > time.time()
    assert 7 in init.user_details[uid]["streak_rewards_claimed"]

    # Milestone 30 (1 Week VIP = 7 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 30, STREAK_REWARDS[30])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (7 * 86400) - 5
    assert 30 in init.user_details[uid]["streak_rewards_claimed"]

    # Milestone 60 (2 Weeks VIP = 14 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 60, STREAK_REWARDS[60])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (14 * 86400) - 5

    # Milestone 120 (3 Weeks VIP = 21 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 120, STREAK_REWARDS[120])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (21 * 86400) - 5

    # Milestone 240 (4 Weeks VIP = 28 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 240, STREAK_REWARDS[240])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (28 * 86400) - 5

    # Milestone 480 (5 Weeks VIP = 35 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 480, STREAK_REWARDS[480])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (35 * 86400) - 5

    # Milestone 960 (6 Weeks VIP = 42 days)
    old_expiry = init.user_details[uid]["subscription_expires"]
    await claim_milestone_reward(bot, uid, 960, STREAK_REWARDS[960])
    assert init.user_details[uid]["subscription_expires"] >= old_expiry + (42 * 86400) - 5


@pytest.mark.asyncio
async def test_session_end_triggers_streak_when_messages_exchanged(monkeypatch):
    monkeypatch.setattr("saveNload.end_chat_session_db", AsyncMock())
    monkeypatch.setattr("saveNload.are_friends_db", AsyncMock(return_value=False))
    monkeypatch.setattr("handlers.rating.ask_for_rating", AsyncMock())

    context = MagicMock()
    context.bot.send_message = AsyncMock()

    u1, u2 = 3010, 3011
    init.user_details[u1] = init._default_user()
    init.user_details[u2] = init._default_user()

    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.active_sessions[u1] = "sess-streak-test"
    init.active_sessions[u2] = "sess-streak-test"

    # 2 messages exchanged
    init.session_messages["sess-streak-test"] = [
        (u1, "Hello partner", time.time()),
        (u2, "Hey there!", time.time()),
    ]

    await end_chat_session(context, u1)

    assert init.user_details[u1]["current_streak"] == 1
    assert init.user_details[u2]["current_streak"] == 1


# ============================================================================
# 3. Upgraded Weekly Leaderboard (/top)
# ============================================================================

@pytest.mark.asyncio
async def test_leaderboard_rendering_and_tabs(monkeypatch):
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)

    # Populate test users
    for i in range(1, 15):
        uid = 4000 + i
        init.user_details[uid] = {
            **init._default_user(),
            "current_streak": i * 2,
            "longest_streak": i * 2 + 5,
            "votes": {"up": i * 10, "down": 0},
            "points": i * 100,
        }

    viewer_id = 4005  # streak = 10, up = 50, pts = 500

    # 1. Streaks Category
    text_streaks = await render_leaderboard_text("streaks", viewer_id)
    assert "🔥 Daily Chat Streaks" in text_streaks
    assert "<blockquote>" in text_streaks
    assert "🥇" in text_streaks
    assert "🥈" in text_streaks
    assert "🥉" in text_streaks
    assert "🎖️⭐" in text_streaks
    assert "4014***" in text_streaks  # Top rank anonymized
    assert "Your Stats:" in text_streaks

    # 2. Karma Category
    text_karma = await render_leaderboard_text("karma", viewer_id)
    assert "⭐ Karma & Upvotes Leaderboard" in text_karma
    assert "👍" in text_karma

    # 3. Games Category
    text_games = await render_leaderboard_text("games", viewer_id)
    assert "🎮 Mini-Games & Points" in text_games
    assert "pts" in text_games


@pytest.mark.asyncio
async def test_show_top_leaderboard_command(monkeypatch):
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)

    user_id = 4050
    init.user_details[user_id] = {**init._default_user(), "gender": "M", "age": 25, "country": "US"}

    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await show_top_leaderboard(update, context)

    assert update.message.reply_text.called
    kwargs = update.message.reply_text.call_args[1]
    assert "Daily Chat Streaks" in kwargs["text"]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_handle_top_callback(monkeypatch):
    monkeypatch.setattr("saveNload.is_pool_ready", lambda: False)

    user_id = 4051
    init.user_details[user_id] = init._default_user()

    update = MagicMock()
    update.effective_user.id = user_id
    query = MagicMock()
    query.data = "top|karma"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update.callback_query = query
    context = MagicMock()

    await handle_top_callback(update, context)

    assert query.edit_message_text.called
    kwargs = query.edit_message_text.call_args[1]
    assert "Karma & Upvotes" in kwargs["text"]


# ============================================================================
# 4. Telegram Stars In-Chat Gifting (/gift)
# ============================================================================

@pytest.mark.asyncio
async def test_gift_command_outside_chat_rejected():
    user_id = 5001
    init.user_details[user_id] = {**init._default_user(), "gender": "M", "age": 22, "country": "UK"}
    init.active_pairs.pop(user_id, None)

    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await gift_command(update, context)

    assert update.message.reply_text.called
    assert "only send gifts during an active chat" in update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_gift_command_inside_chat_shows_catalog():
    u1, u2 = 5002, 5003
    init.user_details[u1] = {**init._default_user(), "gender": "M", "age": 22, "country": "UK"}
    init.user_details[u2] = {**init._default_user(), "gender": "F", "age": 21, "country": "CA"}
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1

    update = MagicMock()
    update.effective_user.id = u1
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await gift_command(update, context)

    assert update.message.reply_text.called
    args = update.message.reply_text.call_args[1]
    assert "Send an Anonymous Gift" in args["text"]
    assert args["reply_markup"] is not None


@pytest.mark.asyncio
async def test_handle_gift_callback_issues_stars_invoice():
    u1, u2 = 5004, 5005
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1

    update = MagicMock()
    update.effective_user.id = u1
    query = MagicMock()
    query.data = "gift|coffee"
    query.answer = AsyncMock()
    update.callback_query = query

    context = MagicMock()
    context.bot.send_invoice = AsyncMock()

    await handle_gift_callback(update, context)

    assert context.bot.send_invoice.called
    inv_args = context.bot.send_invoice.call_args[1]
    assert inv_args["chat_id"] == u1
    assert inv_args["currency"] == "XTR"
    assert inv_args["payload"] == f"gift|coffee|{u2}"


@pytest.mark.asyncio
async def test_gift_payment_fulfillment(monkeypatch):
    monkeypatch.setattr("saveNload.record_payment_transaction_db", AsyncMock(return_value=True))
    monkeypatch.setattr("saveNload.add_subscription_db", AsyncMock())

    buyer = 5010
    recipient = 5011
    init.user_details[buyer] = init._default_user()
    init.user_details[recipient] = {**init._default_user(), "points": 100}

    # 1. Test Pre-checkout approves gift
    pc_update = MagicMock()
    pc_query = MagicMock()
    pc_query.invoice_payload = f"gift|crown|{recipient}"
    pc_query.answer = AsyncMock()
    pc_update.pre_checkout_query = pc_query
    context = MagicMock()

    await handle_pre_checkout(pc_update, context)
    assert pc_query.answer.called
    assert pc_query.answer.call_args[1]["ok"] is True

    # 2. Test Successful Payment fulfills Crown gift (500 pts + 1d VIP)
    sp_update = MagicMock()
    sp_update.effective_user.id = buyer
    sp_update.message.reply_text = AsyncMock()
    payment = MagicMock()
    payment.invoice_payload = f"gift|crown|{recipient}"
    payment.telegram_payment_charge_id = "test_charge_stars_777"
    sp_update.message.successful_payment = payment
    context.bot.send_message = AsyncMock()

    await handle_successful_payment(sp_update, context)

    # Recipient points increased by 500
    assert init.user_details[recipient]["points"] == 600
    # Recipient granted VIP access
    assert init.user_details[recipient]["subscription_expires"] > time.time()

    # Buyer notified
    assert sp_update.message.reply_text.called
    assert "Gift Delivered" in sp_update.message.reply_text.call_args[1]["text"]

    # Recipient received celebration notice
    assert context.bot.send_message.called
    rec_args = context.bot.send_message.call_args[1]
    assert rec_args["chat_id"] == recipient
    assert "WOW! Your chat partner sent you a Gift" in rec_args["text"]
    assert "Royal Crown" in rec_args["text"]
