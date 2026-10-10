import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import BotCommandScopeAllGroupChats, BotCommandScopeChat

import init
from group_helper import (
    is_group_chat, delete_admin_command, is_group_admin, resolve_target,
    get_group_redirect_keyboard
)
from commands.start import start
from commands.find import find
from commands.next import skip_partner
from commands.stop import stop
from commands.nudge import handle_nudge, status_command
from commands.link import link_command
from media_privacy import handle_private_command
from commands.profile import show_profile
from commands.subscribe import show_subscribe_menu
from handlers.friends import show_friends_menu, send_friend_request, handle_friend_request_response
from commands.block import block_command
from commands.call import call_command
from commands.gift import gift_command
from handlers.payments import handle_successful_payment
from commands.games import (
    games_menu, handle_group_game_selection, handle_group_challenge_accept,
    handle_group_challenge_cancel
)
from commands.cancel import cancel
from commands.admin_commands import (
    admin_stats, queue_stats, check_user, ban_user, unban_user,
    giveaway_subscription, broadcast, connect, referral_scheme_command,
    campaign_command
)
from rush_hour import rush_hour_command
from relay import relay_message, relay_reaction, relay_edited_message
from main import set_commands


@pytest.fixture(autouse=True)
def clean_group_test_state():
    init.user_details.clear()
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.waiting_users.clear()
    init.group_games.clear()
    init.username_to_id.clear()
    init.pending_friend_requests.clear()
    init.ADMIN_IDS = {99999}
    init.OWNER = "99999"
    yield
    init.user_details.clear()
    init.active_pairs.clear()
    init.active_sessions.clear()
    init.waiting_users.clear()
    init.group_games.clear()
    init.username_to_id.clear()
    init.pending_friend_requests.clear()


def _make_group_update(chat_id=-1001234567, user_id=111, chat_type="supergroup", text="", reply_to=None):
    update = MagicMock()
    update.effective_chat = MagicMock()
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_chat.title = "Test Lounge"

    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = f"User{user_id}"
    update.effective_user.username = f"user_{user_id}"
    update.effective_user.full_name = f"User {user_id}"

    update.message = MagicMock()
    update.message.chat = update.effective_chat
    update.message.chat_id = chat_id
    update.message.from_user = update.effective_user
    update.message.text = text
    update.message.reply_to_message = reply_to
    update.message.reply_text = AsyncMock()
    update.message.delete = AsyncMock()

    update.effective_message = update.message
    return update


# -------------------------------------------------------------
# 1. GROUP HELPER TESTS
# -------------------------------------------------------------

def test_is_group_chat():
    u_group = _make_group_update(chat_type="group")
    u_supergroup = _make_group_update(chat_type="supergroup")
    u_private = _make_group_update(chat_type="private")
    u_channel = _make_group_update(chat_type="channel")

    assert is_group_chat(u_group) is True
    assert is_group_chat(u_supergroup) is True
    assert is_group_chat(u_private) is False
    assert is_group_chat(u_channel) is False


@pytest.mark.asyncio
async def test_delete_admin_command():
    u_group = _make_group_update(chat_type="supergroup")
    u_private = _make_group_update(chat_type="private")
    context = MagicMock()

    res_group = await delete_admin_command(u_group, context)
    assert res_group is True
    u_group.message.delete.assert_called_once()

    res_priv = await delete_admin_command(u_private, context)
    assert res_priv is False
    u_private.message.delete.assert_not_called()


@pytest.mark.asyncio
async def test_is_group_admin():
    context = MagicMock()
    chat_id = -100123

    # Global bot admin (99999 is in init.ADMIN_IDS)
    assert await is_group_admin(context, chat_id, 99999) is True

    # Group administrator via Telegram API
    member_admin = MagicMock()
    member_admin.status = "administrator"
    context.bot.get_chat_member = AsyncMock(return_value=member_admin)
    assert await is_group_admin(context, chat_id, 222) is True

    # Regular group member
    member_regular = MagicMock()
    member_regular.status = "member"
    context.bot.get_chat_member = AsyncMock(return_value=member_regular)
    assert await is_group_admin(context, chat_id, 333) is False


@pytest.mark.asyncio
async def test_resolve_target():
    # 1. By reply
    reply_user = MagicMock()
    reply_user.id = 555
    reply_user.first_name = "TargetBob"
    reply_user.username = "targetbob"

    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    u_reply = _make_group_update(reply_to=reply_msg)
    context = MagicMock()
    res = await resolve_target(u_reply, context)
    assert res == (555, "@targetbob")
    assert init.username_to_id["targetbob"] == 555

    # 2. By @username arg
    u_arg = _make_group_update()
    context.args = ["@targetbob"]
    res2 = await resolve_target(u_arg, context)
    assert res2 == (555, "@targetbob")

    # 3. By numeric ID
    context.args = ["777"]
    res3 = await resolve_target(u_arg, context)
    assert res3 == (777, "User 777")


# -------------------------------------------------------------
# 2. DM-ONLY REDIRECT COMMANDS IN GROUPS
# -------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("cmd_func", [
    start, find, skip_partner, stop, status_command, link_command, handle_private_command
])
async def test_group_redirect_commands(cmd_func):
    update = _make_group_update(user_id=111)
    context = MagicMock()
    context.bot.username = "AnonChatZoneBot"

    await cmd_func(update, context)

    assert update.message.reply_text.called
    call_args = update.message.reply_text.call_args
    sent_text = call_args[1].get("text", "") or (call_args[0][0] if call_args[0] else "")
    keyboard = call_args[1].get("reply_markup")

    assert "This command cannot be used inside groups!" in sent_text
    assert keyboard is not None
    button_url = keyboard.inline_keyboard[0][0].url
    assert "https://t.me/AnonChatZoneBot" in button_url


# -------------------------------------------------------------
# 3. PRIVATE DM DELIVERIES FROM GROUPS (Profile, Subscribe, Friends)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_profile_and_subscribe_delivery():
    user_id = 111
    init.user_details[user_id] = {
        **init._default_user(),
        "gender": "M",
        "age": 25,
        "country": "US",
        "points": 50
    }
    update = _make_group_update(user_id=user_id)
    context = MagicMock()
    context.bot.username = "AnonChatZoneBot"
    context.bot.send_message = AsyncMock(return_value=MagicMock())

    # /profile
    await show_profile(update, context)
    assert update.message.reply_text.called
    assert "I have sent your profile to your private DM!" in update.message.reply_text.call_args[1]["text"]
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == user_id
    assert "Your Profile" in context.bot.send_message.call_args[1]["text"]

    # /subscribe
    context.bot.send_message.reset_mock()
    update.message.reply_text.reset_mock()
    await show_subscribe_menu(update, context)
    assert update.message.reply_text.called
    assert "I have sent the VIP subscription tiers to your private DM!" in update.message.reply_text.call_args[1]["text"]
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == user_id
    assert "Chat Zone Subscription" in context.bot.send_message.call_args[1]["text"]


@pytest.mark.asyncio
async def test_group_friends_menu_delivery():
    user_id = 111
    init.user_details[user_id] = init._default_user()
    update = _make_group_update(user_id=user_id)
    context = MagicMock()
    context.bot.username = "AnonChatZoneBot"
    context.bot.send_message = AsyncMock(return_value=MagicMock())

    with patch("handlers.friends.get_user_friends_db", AsyncMock(return_value=[])):
        await show_friends_menu(update, context, page=0)

    assert update.message.reply_text.called
    assert "I have sent your anonymous friends list to your private DM!" in update.message.reply_text.call_args[1]["text"]
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == user_id


# -------------------------------------------------------------
# 4. SOCIAL COMMANDS IN GROUPS (/nudge, /block, /friendreq, /call, /gift)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_nudge_tags_user():
    caller_id = 111
    target_id = 222
    init.user_details[caller_id] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[target_id] = {**init._default_user(), "gender": "F", "age": 22, "country": "US"}

    reply_user = MagicMock()
    reply_user.id = target_id
    reply_user.username = "alice"
    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    update = _make_group_update(user_id=caller_id, reply_to=reply_msg)
    context = MagicMock()

    await handle_nudge(update, context)
    assert update.message.reply_text.called
    text = update.message.reply_text.call_args[1]["text"]
    assert "nudged you! Wake up!" in text
    assert "@alice" in text


@pytest.mark.asyncio
async def test_group_block_by_reply():
    user_id = 111
    target_id = 222
    init.user_details[user_id] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[target_id] = {**init._default_user(), "gender": "F", "age": 22, "country": "US"}

    reply_user = MagicMock()
    reply_user.id = target_id
    reply_user.username = "baduser"
    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    update = _make_group_update(user_id=user_id, reply_to=reply_msg)
    context = MagicMock()

    with patch("commands.block.can_user_block", AsyncMock(return_value=(True, 0, 5))), \
         patch("commands.block.add_user_block", AsyncMock(return_value=True)):
        await block_command(update, context)

    assert update.message.reply_text.called
    text = update.message.reply_text.call_args[1]["text"]
    assert "no longer be paired with" in text


@pytest.mark.asyncio
async def test_group_friend_request_flow():
    sender_id = 111
    target_id = 222
    init.user_details[sender_id] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[target_id] = {**init._default_user(), "gender": "F", "age": 22, "country": "US"}

    reply_user = MagicMock()
    reply_user.id = target_id
    reply_user.username = "targetbob"
    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    update = _make_group_update(user_id=sender_id, reply_to=reply_msg)
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    with patch("handlers.friends.get_friend_count_db", AsyncMock(return_value=0)), \
         patch("handlers.friends.are_friends_db", AsyncMock(return_value=False)):
        await send_friend_request(update, context)

    assert update.message.reply_text.called
    call_kwargs = update.message.reply_text.call_args[1]
    card_text = call_kwargs["text"]
    keyboard = call_kwargs["reply_markup"]

    assert "Anonymous Friend Request" in card_text
    acc_cb = keyboard.inline_keyboard[0][0].callback_data
    req_id = acc_cb.split("|")[1]
    assert req_id in init.pending_friend_requests

    # Test unauthorized user clicking accept -> gets alert
    unauth_update = MagicMock()
    unauth_query = MagicMock()
    unauth_query.data = f"freq_acc|{req_id}"
    unauth_query.answer = AsyncMock()
    unauth_update.callback_query = unauth_query
    unauth_update.effective_user.id = 333  # Random member

    await handle_friend_request_response(unauth_update, context)
    assert unauth_query.answer.called
    assert unauth_query.answer.call_args[1].get("show_alert") is True
    assert "Only the invited person can accept or decline" in unauth_query.answer.call_args[1].get("text", "")

    # Test authorized target clicking accept
    auth_update = MagicMock()
    auth_query = MagicMock()
    auth_query.data = f"freq_acc|{req_id}"
    auth_query.answer = AsyncMock()
    auth_query.edit_message_text = AsyncMock()
    auth_update.callback_query = auth_query
    auth_update.effective_user.id = target_id

    with patch("saveNload.add_friend_pair_db", AsyncMock(return_value=True)):
        await handle_friend_request_response(auth_update, context)

    auth_query.edit_message_text.assert_called_once()
    assert "accepted @user_111's friend request!" in auth_query.edit_message_text.call_args[1]["text"]


@pytest.mark.asyncio
async def test_group_call_command():
    caller_id = 111
    target_id = 222
    init.user_details[caller_id] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[target_id] = {**init._default_user(), "gender": "F", "age": 22, "country": "US"}

    reply_user = MagicMock()
    reply_user.id = target_id
    reply_user.username = "targetbob"
    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    update = _make_group_update(user_id=caller_id, reply_to=reply_msg)
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock())

    await call_command(update, context)
    assert update.message.reply_text.called
    assert "anonymous voice call request" in update.message.reply_text.call_args[1]["text"]
    assert context.bot.send_message.called
    call_dm = context.bot.send_message.call_args[1]
    assert call_dm["chat_id"] == target_id
    assert "Incoming Anonymous Voice Call Request!" in call_dm["text"]


@pytest.mark.asyncio
async def test_group_gift_command_and_fulfillment():
    sender_id = 111
    target_id = 222
    init.user_details[sender_id] = {**init._default_user(), "gender": "M", "age": 20, "country": "US"}
    init.user_details[target_id] = {**init._default_user(), "gender": "F", "age": 22, "country": "US", "points": 100}

    reply_user = MagicMock()
    reply_user.id = target_id
    reply_user.username = "targetbob"
    reply_msg = MagicMock()
    reply_msg.from_user = reply_user

    update = _make_group_update(user_id=sender_id, reply_to=reply_msg)
    context = MagicMock()
    context.bot.send_message = AsyncMock(return_value=MagicMock())

    await gift_command(update, context)
    assert update.message.reply_text.called
    assert "preparing a gift" in update.message.reply_text.call_args[1]["text"]
    assert context.bot.send_message.called
    dm_gift = context.bot.send_message.call_args[1]
    assert dm_gift["chat_id"] == sender_id
    cb = dm_gift["reply_markup"].inline_keyboard[0][0].callback_data
    assert f"gift|coffee|{target_id}|{update.effective_chat.id}" in cb

    # Test fulfillment announces celebration in group
    sp_update = MagicMock()
    sp_update.effective_user.id = sender_id
    sp_update.message.reply_text = AsyncMock()
    payment = MagicMock()
    payment.invoice_payload = f"gift|crown|{target_id}|{update.effective_chat.id}"
    payment.telegram_payment_charge_id = "test_stars_999"
    sp_update.message.successful_payment = payment

    with patch("saveNload.record_payment_transaction_db", AsyncMock(return_value=True)), \
         patch("saveNload.add_subscription_db", AsyncMock()):
        await handle_successful_payment(sp_update, context)

    # Verified group announcement was posted!
    group_calls = [c for c in context.bot.send_message.call_args_list if c[1].get("chat_id") == update.effective_chat.id]
    assert len(group_calls) > 0
    assert "A Gift has been sent in Chat Zone!" in group_calls[0][1]["text"]


# -------------------------------------------------------------
# 5. GROUP GAMES SYSTEM (Open challenge, acceptance, cancellation)
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_games_flow():
    p1 = 111
    p2 = 222
    init.user_details[p1] = {**init._default_user(), "gender": "M", "age": 25, "country": "US"}
    init.user_details[p2] = {**init._default_user(), "gender": "F", "age": 24, "country": "UK"}

    update = _make_group_update(user_id=p1)
    context = MagicMock()

    # 1. /games posts game selection menu
    await games_menu(update, context)
    assert update.message.reply_text.called
    sel_kb = update.message.reply_text.call_args[1]["reply_markup"]
    assert sel_kb.inline_keyboard[0][0].callback_data.startswith("grpgame|")

    # 2. Challenger selects Rock Paper Scissors
    sel_update = MagicMock()
    sel_query = MagicMock()
    sel_query.data = f"grpgame|rps|{p1}"
    sel_query.message.message_id = 99
    sel_query.edit_message_text = AsyncMock()
    sel_query.answer = AsyncMock()
    sel_update.callback_query = sel_query
    sel_update.effective_user.id = p1
    sel_update.effective_user.username = "user_p1"
    sel_update.effective_user.first_name = "UserP1"
    sel_update.effective_chat.id = update.effective_chat.id

    await handle_group_game_selection(sel_update, context)
    assert sel_query.edit_message_text.called
    chal_text = sel_query.edit_message_text.call_args[1]["text"]
    assert "Open Challenge: Rock Paper Scissors" in chal_text

    chal_id = list(init.group_games.keys())[0]

    # 3. Opponent accepts challenge
    acc_update = MagicMock()
    acc_query = MagicMock()
    acc_query.data = f"grp_acc|{chal_id}"
    acc_query.edit_message_text = AsyncMock()
    acc_query.answer = AsyncMock()
    acc_update.callback_query = acc_query
    acc_update.effective_user.id = p2
    acc_update.effective_user.first_name = "Alice"
    acc_update.effective_user.username = "alice"
    acc_update.effective_chat.id = update.effective_chat.id

    context.bot.send_message = AsyncMock()
    with patch("games.rps.send_round", AsyncMock()):
        await handle_group_challenge_accept(acc_update, context)

    # Challenger notified in DM
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == p1
    assert "accepted your challenge in Rock Paper Scissors" in context.bot.send_message.call_args[1]["text"]

    # Challenge card updated
    assert acc_query.edit_message_text.called
    assert "Duel Accepted!" in acc_query.edit_message_text.call_args[1]["text"]


# -------------------------------------------------------------
# 6. ADMIN CONFIDENTIALITY AND AUTO-DELETION IN GROUPS
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_commands_confidentiality_and_auto_delete():
    admin_id = 99999
    update = _make_group_update(user_id=admin_id)
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    # 1. /stats -> deleted in group, delivered secretly to admin DM
    await admin_stats(update, context)
    update.message.delete.assert_called_once()
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == admin_id
    assert "System & Operational Stats" in context.bot.send_message.call_args[1]["text"]

    # 2. /queue -> deleted in group, delivered secretly to admin DM
    update.message.delete.reset_mock()
    context.bot.send_message.reset_mock()
    await queue_stats(update, context)
    update.message.delete.assert_called_once()
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == admin_id
    assert "Queue Overview" in context.bot.send_message.call_args[1]["text"]

    # 3. /checkuser -> deleted in group, report delivered secretly to admin DM
    update.message.delete.reset_mock()
    context.bot.send_message.reset_mock()
    context.args = ["111"]
    init.user_details[111] = {**init._default_user(), "gender": "M", "country": "US"}

    await check_user(update, context)
    update.message.delete.assert_called_once()
    assert context.bot.send_message.called
    assert context.bot.send_message.call_args[1]["chat_id"] == admin_id
    assert "<b>User</b> <code>111</code>" in context.bot.send_message.call_args[1]["text"]

    # 4. DM-restricted admin commands (/broadcast, /connect, /referral, /campaign, /rushhour)
    for admin_cmd in [broadcast, connect, referral_scheme_command, campaign_command, rush_hour_command]:
        update.message.delete.reset_mock()
        context.bot.send_message.reset_mock()
        await admin_cmd(update, context)
        update.message.delete.assert_called_once()
        assert context.bot.send_message.called
        assert context.bot.send_message.call_args[1]["chat_id"] == admin_id
        assert "restricted to private DMs only" in context.bot.send_message.call_args[1]["text"]


# -------------------------------------------------------------
# 7. GROUP SCOPE NEVER EXPOSES ADMIN COMMANDS
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_group_command_scope_confidentiality():
    mock_app = MagicMock()
    mock_app.bot.set_my_commands = AsyncMock()

    await set_commands(mock_app)

    # Find the set_my_commands call with BotCommandScopeAllGroupChats
    group_calls = [
        call for call in mock_app.bot.set_my_commands.call_args_list
        if isinstance(call[1].get("scope"), BotCommandScopeAllGroupChats)
    ]
    assert len(group_calls) == 1, "Must set command scope specifically for all group chats!"

    group_cmd_names = [c.command for c in group_calls[0][0][0]]

    # Ensure all user commands are present
    assert "start" in group_cmd_names
    assert "help" in group_cmd_names
    assert "games" in group_cmd_names
    assert "nudge" in group_cmd_names

    # CRITICAL: Verify NO admin commands are exposed in group chat menus!
    admin_cmds = ["stats", "queue", "connect", "checkuser", "ban", "unban", "giveaway", "referral", "broadcast", "campaign", "rushhour"]
    for adm in admin_cmds:
        assert adm not in group_cmd_names, f"Admin command {adm} MUST NOT be disclosed in group menus!"


# -------------------------------------------------------------
# 8. ZERO GROUP SPAM IN RELAY
# -------------------------------------------------------------

@pytest.mark.asyncio
async def test_relay_zero_spam_in_groups():
    update = _make_group_update(text="Hello everyone in the group!")
    context = MagicMock()
    context.bot.send_message = AsyncMock()

    # Normal message in group
    await relay_message(update, context)
    update.message.reply_text.assert_not_called()
    context.bot.send_message.assert_not_called()

    # Reaction in group
    react_update = MagicMock()
    react_update.message_reaction = MagicMock()
    react_update.message_reaction.chat = update.effective_chat
    await relay_reaction(react_update, context)
    context.bot.send_message.assert_not_called()

    # Edited message in group
    edit_update = MagicMock()
    edit_update.edited_message = update.message
    await relay_edited_message(edit_update, context)
    context.bot.send_message.assert_not_called()
