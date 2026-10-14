import time
import pytest
from unittest.mock import AsyncMock, MagicMock

import init
import subscription
from commands.prune import prune_command
from commands.subscribe import show_subscribe_menu, handle_tier_selection
from commands.profile import _build_profile_text
from commands.leaderboard import render_leaderboard_text


@pytest.fixture(autouse=True)
def clean_state():
    init.active_pairs.clear()
    init.message_map.clear()
    init.user_details.clear()
    yield
    init.active_pairs.clear()
    init.message_map.clear()
    init.user_details.clear()


def test_tier_definitions_and_badges():
    """Verifies that all 4 tiers have correct pricing, badges, and helper functions work."""
    # Free member
    u_free = 1001
    assert subscription.get_tier_badge(u_free) == "💬"
    assert "Free Member" in subscription.get_tier_display_name(u_free)
    assert not subscription.has_tier(u_free, "daily")
    assert not subscription.has_tier(u_free, "weekly")

    # Daily VIP
    u_daily = 1002
    subscription.grant_subscription(u_daily, "daily")
    assert subscription.TIERS["daily"]["stars"] == 25
    assert subscription.TIERS["daily"]["direct_price"] == "₹20 / $0.24"
    assert subscription.get_tier_badge(u_daily) == "⚡"
    assert subscription.has_tier(u_daily, "daily") is True
    assert subscription.has_tier(u_daily, "weekly") is False
    assert subscription.has_tier(u_daily, "monthly") is False

    # Weekly VIP
    u_weekly = 1003
    subscription.grant_subscription(u_weekly, "weekly")
    assert subscription.TIERS["weekly"]["stars"] == 125
    assert subscription.TIERS["weekly"]["direct_price"] == "₹100 / $1.20"
    assert subscription.get_tier_badge(u_weekly) == "✨"
    assert subscription.has_tier(u_weekly, "daily") is True
    assert subscription.has_tier(u_weekly, "weekly") is True
    assert subscription.has_tier(u_weekly, "monthly") is False

    # Monthly VIP
    u_monthly = 1004
    subscription.grant_subscription(u_monthly, "monthly")
    assert subscription.TIERS["monthly"]["stars"] == 450
    assert subscription.TIERS["monthly"]["direct_price"] == "₹300 / $3.60"
    assert subscription.get_tier_badge(u_monthly) == "🌙"
    assert subscription.has_tier(u_monthly, "weekly") is True
    assert subscription.has_tier(u_monthly, "monthly") is True
    assert subscription.has_tier(u_monthly, "yearly") is False

    # Yearly VIP
    u_yearly = 1005
    subscription.grant_subscription(u_yearly, "yearly")
    assert subscription.TIERS["yearly"]["stars"] == 4500
    assert subscription.TIERS["yearly"]["direct_price"] == "₹2,400 / $28.80"
    assert subscription.get_tier_badge(u_yearly) == "👑"
    assert subscription.has_tier(u_yearly, "daily") is True
    assert subscription.has_tier(u_yearly, "weekly") is True
    assert subscription.has_tier(u_yearly, "monthly") is True
    assert subscription.has_tier(u_yearly, "yearly") is True


@pytest.mark.asyncio
async def test_prune_command_not_in_chat():
    """Verify /prune fails gracefully when user is not in an active chat."""
    update = MagicMock()
    update.effective_user.id = 5001
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await prune_command(update, context)
    update.message.reply_text.assert_called_once()
    assert "not currently in an active chat" in update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_prune_command_no_reply():
    """Verify /prune shows usage hint if not sent as a reply."""
    u1, u2 = 5002, 5003
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.user_details[u1] = init._default_user()

    update = MagicMock()
    update.effective_user.id = u1
    update.message.reply_to_message = None
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await prune_command(update, context)
    update.message.reply_text.assert_called_once()
    assert "Reply to any message" in update.message.reply_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_prune_command_free_user_upsell():
    """Verify /prune prompts free user to upgrade to VIP, and allows Daily VIP."""
    u1, u2 = 5004, 5005
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.user_details[u1] = init._default_user()

    # Free user is prompted to unlock VIP
    update = MagicMock()
    update.effective_user.id = u1
    update.message.reply_to_message = MagicMock(message_id=901)
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await prune_command(update, context)
    update.message.reply_text.assert_called_once()
    assert "Two-Way Wipe (/prune) is a VIP Feature" in update.message.reply_text.call_args[1]["text"]

    # Daily VIP user is allowed to /prune (all VIP tiers have full powers)
    subscription.grant_subscription(u1, "daily")
    update.message.reply_text.reset_mock()
    context.bot.delete_message = AsyncMock(return_value=True)
    await prune_command(update, context)
    # delete_message should be called (not blocked by upsell)
    assert context.bot.delete_message.called


@pytest.mark.asyncio
async def test_prune_command_vip_success():
    """Verify /prune deletes message on both sides and cleans up message_map."""
    u1, u2 = 5006, 5007
    init.active_pairs[u1] = u2
    init.active_pairs[u2] = u1
    init.user_details[u1] = init._default_user()
    subscription.grant_subscription(u1, "daily")  # Even Daily VIP gets prune!

    # Simulate mapped messages: user1 msg 101 corresponds to partner msg 201
    init.message_map[u1] = {101: (u2, 201)}
    init.message_map[u2] = {201: (u1, 101)}

    update = MagicMock()
    update.effective_user.id = u1
    update.message.message_id = 105  # The /prune command message ID
    update.message.reply_to_message = MagicMock(message_id=101)
    context = MagicMock()
    context.bot.delete_message = AsyncMock(return_value=True)

    await prune_command(update, context)

    # 1. Target message deleted in sender's chat (101)
    # 2. Command message deleted in sender's chat (105)
    # 3. Target message deleted in partner's chat (201)
    assert context.bot.delete_message.call_count == 3
    calls = context.bot.delete_message.call_args_list
    assert calls[0][1] == {"chat_id": u1, "message_id": 101}
    assert calls[1][1] == {"chat_id": u1, "message_id": 105}
    assert calls[2][1] == {"chat_id": u2, "message_id": 201}

    # Verify message_map entries cleaned up
    assert 101 not in init.message_map[u1]
    assert 201 not in init.message_map[u2]


@pytest.mark.asyncio
async def test_subscribe_menu_and_comparison_callback():
    """Verify /subscribe layout and compare matrix callback."""
    u = 5008
    init.user_details[u] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}

    update = MagicMock()
    update.effective_user.id = u
    update.effective_user.username = "chattester"
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    # Main /subscribe view
    await show_subscribe_menu(update, context)
    update.message.reply_text.assert_called_once()
    main_text = update.message.reply_text.call_args[1]["text"]
    assert "VIP Membership" in main_text
    assert "25 ⭐" in main_text
    assert "125 ⭐" in main_text
    assert "450 ⭐" in main_text
    assert "4,500 ⭐" in main_text
    kb = update.message.reply_text.call_args[1]["reply_markup"].inline_keyboard
    assert any(b.callback_data == "sub|compare" for row in kb for b in row)

    # Tap compare callback
    cb_update = MagicMock()
    cb_update.callback_query.data = "sub|compare"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()

    await handle_tier_selection(cb_update, context)
    cb_update.callback_query.edit_message_text.assert_called_once()
    compare_text = cb_update.callback_query.edit_message_text.call_args[1]["text"]
    assert "VIP PERKS COMPARISON MATRIX" in compare_text
    assert "Two-Way Wipe" in compare_text
    comp_kb = cb_update.callback_query.edit_message_text.call_args[1]["reply_markup"].inline_keyboard
    assert any(b.callback_data == "sub|back" for row in comp_kb for b in row)


@pytest.mark.asyncio
async def test_badges_in_profile_and_leaderboard():
    """Verify tier badges appear in /profile and /leaderboard."""
    u_free = 6001
    u_vip = 6002
    init.user_details[u_free] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[u_vip] = {**init._default_user(), "gender": "F", "age": 22, "country": "US", "points": 500}
    subscription.grant_subscription(u_vip, "yearly")

    context = MagicMock()
    context.bot.get_chat = AsyncMock(return_value=MagicMock(full_name="Free User", username="freeuser"))

    # Profile shows badge
    prof_free = await _build_profile_text(u_free, context)
    assert "💬 Free Member" in prof_free

    context.bot.get_chat = AsyncMock(return_value=MagicMock(full_name="VIP User", username="vipuser"))
    prof_vip = await _build_profile_text(u_vip, context)
    assert "👑 Yearly VIP" in prof_vip

    # Leaderboard shows badge
    board_text = await render_leaderboard_text("games", u_vip)
    assert "👑" in board_text


@pytest.mark.asyncio
async def test_badge_visibility_toggle():
    """Verify users can toggle their badge off in profile."""
    from handlers.edit import handle_edit_selection

    u = 7001
    init.user_details[u] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    subscription.grant_subscription(u, "monthly")

    assert init.user_details[u].get("show_badge", True) is True
    assert subscription.get_tier_badge(u) == "🌙"

    # Simulate toggle_badge callback
    cb_update = MagicMock()
    cb_update.callback_query.from_user.id = u
    cb_update.callback_query.data = "edit|toggle_badge"
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.edit_message_text = AsyncMock()
    context = MagicMock()
    context.bot.get_chat = AsyncMock(return_value=MagicMock(full_name="User", username="user"))

    await handle_edit_selection(cb_update, context)

    # Now badge is hidden
    assert init.user_details[u]["show_badge"] is False
    assert subscription.get_tier_badge(u) == ""

    # Toggle back on
    await handle_edit_selection(cb_update, context)
    assert init.user_details[u]["show_badge"] is True
    assert subscription.get_tier_badge(u) == "🌙"


def test_admin_contact_url_points_to_owner(monkeypatch):
    """Verify get_admin_contact_url returns owner's DM and not channel."""
    from commands.subscribe import get_admin_contact_url

    # Case 1: Numeric owner ID -> tg://user?id=...
    monkeypatch.setenv("OWNER", "123456789")
    monkeypatch.delenv("ADMIN_CONTACT_URL", raising=False)
    monkeypatch.delenv("OWNER_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    import init
    init.OWNER = "123456789"
    assert get_admin_contact_url() == "tg://user?id=123456789"

    # Case 2: Owner username
    monkeypatch.setenv("OWNER_USERNAME", "@the_real_owner")
    assert get_admin_contact_url() == "https://t.me/the_real_owner"

