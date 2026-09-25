import time
import random
import uuid
from typing import Optional
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call
from session_manager import is_in_chat, get_partner, start_chat_session, IN_CHAT_KEYBOARD
from matchmaking import dequeue_user
from subscription import get_friend_limit
from saveNload import (
    get_user_friends_db,
    get_friend_count_db,
    get_friend_card_db,
    are_friends_db,
    deduplicate_friend_nickname,
    add_friend_pair_db,
    update_friend_nickname_db,
    update_friend_note_db,
    toggle_friend_favorite_db,
    remove_friend_pair_db,
)

DEFAULT_NICKNAMES = [
    "Midnight Wanderer", "Starlight Echo", "Velvet Mirage",
    "Mystic Fox", "Cosmic Nomad", "Neon Shadow",
    "Solaris", "Zephyr", "Aurora", "Orion",
    "Lunar Breeze", "Solstice", "Echo", "Astral Pilot"
]

PAGE_SIZE = 8
REQUEST_TIMEOUT = 120  # 2 minutes


def _format_date(val) -> str:
    if isinstance(val, datetime):
        return val.strftime("%b %d, %Y")
    return "Recently"


async def send_friend_request(update: Update, context: ContextTypes.DEFAULT_TYPE, target_id: Optional[int] = None):
    """
    Sends a mutual friend request to the current or recently ended partner.
    Can be called via /friendreq in chat or by tapping the end-of-chat inline button.
    """
    user_id = update.effective_user.id

    if target_id is None:
        if not is_in_chat(user_id):
            if update.message:
                await safe_tele_func_call(
                    update.message.reply_text,
                    text="⚠️ <b>You are not in a chat right now.</b>\nUse /friendreq while in a chat to add your partner!",
                    parse_mode="HTML",
                )
            return
        target_id = get_partner(user_id)

    if not target_id or target_id == user_id:
        return

    # Check friend limit
    user_count = await get_friend_count_db(user_id)
    user_limit = get_friend_limit(user_id)
    if user_count >= user_limit:
        msg_text = f"⚠️ <b>Friends list full ({user_count}/{user_limit}).</b>\nUpgrade your tier for +16 more friend slots!"
        if update.callback_query:
            await safe_tele_func_call(update.callback_query.answer, text="Friends list full!", show_alert=True)
            await safe_tele_func_call(update.callback_query.edit_message_text, text=msg_text, parse_mode="HTML")
        elif update.message:
            await safe_tele_func_call(update.message.reply_text, text=msg_text, parse_mode="HTML")
        return

    if await are_friends_db(user_id, target_id):
        already_text = "⭐ <b>You are already friends with this user!</b> Check /friends."
        if update.callback_query:
            await safe_tele_func_call(update.callback_query.answer, text="Already friends!", show_alert=True)
        elif update.message:
            await safe_tele_func_call(update.message.reply_text, text=already_text, parse_mode="HTML")
        return

    req_id = str(uuid.uuid4())[:8]
    init.pending_friend_requests[req_id] = {
        "sender_id": user_id,
        "target_id": target_id,
        "created_at": time.time(),
    }

    # Notify partner with Accept/Decline buttons
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"freq_acc|{req_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"freq_dec|{req_id}"),
        ]
    ])

    sent_msg = await safe_tele_func_call(
        context.bot.send_message,
        chat_id=target_id,
        text="⭐ <b>Your partner wants to add you to their Anonymous Friends List!</b>\n<i>You can chat again anytime without revealing usernames or phone numbers. Accept?</i>",
        parse_mode="HTML",
        reply_markup=keyboard,
    )

    if update.callback_query:
        await safe_tele_func_call(update.callback_query.answer, text="Friend request sent!")
        await safe_tele_func_call(
            update.callback_query.edit_message_text,
            text="⭐ <b>Friend request sent! Waiting for your partner to accept...</b>",
            parse_mode="HTML",
        )
    elif update.message:
        await safe_tele_func_call(
            update.message.reply_text,
            text="⭐ <b>Friend request sent! Waiting for your partner to accept...</b>",
            parse_mode="HTML",
        )


async def handle_friend_request_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Accept or Decline on in-flight friend requests."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    parts = (query.data or "").split("|")
    action = parts[0]
    req_id = parts[1] if len(parts) > 1 else ""

    req_data = init.pending_friend_requests.pop(req_id, None)
    if not req_data:
        await safe_tele_func_call(query.edit_message_text, text="⏳ <b>Friend request expired.</b>", parse_mode="HTML")
        return

    sender_id = req_data["sender_id"]
    target_id = req_data["target_id"]

    if user_id != target_id:
        return

    if action == "freq_dec":
        await safe_tele_func_call(query.edit_message_text, text="❌ <b>Friend request declined.</b>", parse_mode="HTML")
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=sender_id,
            text="ℹ️ <b>Your partner declined the friend request.</b>",
            parse_mode="HTML",
        )
        return

    # Check target friend limits
    target_count = await get_friend_count_db(target_id)
    target_limit = get_friend_limit(target_id)
    if target_count >= target_limit:
        await safe_tele_func_call(
            query.edit_message_text,
            text=f"⚠️ <b>Your friends list is full ({target_count}/{target_limit}). Could not accept.</b>",
            parse_mode="HTML",
        )
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=sender_id,
            text="⚠️ <b>Friend request could not be accepted: Partner's friends list is full.</b>",
            parse_mode="HTML",
        )
        return

    # Pick initial default names from random pool
    base_name1 = random.choice(DEFAULT_NICKNAMES)
    base_name2 = random.choice([n for n in DEFAULT_NICKNAMES if n != base_name1] or DEFAULT_NICKNAMES)

    name_for_sender = await deduplicate_friend_nickname(sender_id, base_name1)
    name_for_target = await deduplicate_friend_nickname(target_id, base_name2)

    success = await add_friend_pair_db(sender_id, target_id, name_for_sender, name_for_target)
    if success:
        await safe_tele_func_call(
            query.edit_message_text,
            text=f"🎉 <b>Friend request accepted!</b>\nYour partner is saved as <b>{name_for_target}</b>.\nGo to /friends to customize their nickname or note anytime!",
            parse_mode="HTML",
        )
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=sender_id,
            text=f"🎉 <b>Your partner accepted your friend request!</b>\nSaved as <b>{name_for_sender}</b>.\nGo to /friends to view your friends list!",
            parse_mode="HTML",
        )
    else:
        await safe_tele_func_call(query.edit_message_text, text="⚠️ <b>Failed to add friend. Try again later.</b>", parse_mode="HTML")


async def show_friends_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    """Displays paginated friends list with 8 friends per page."""
    user_id = update.effective_user.id
    friends = await get_user_friends_db(user_id)
    total_count = len(friends)
    friend_limit = get_friend_limit(user_id)

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start_idx = page * PAGE_SIZE
    page_friends = friends[start_idx:start_idx + PAGE_SIZE]

    buttons = []
    if not page_friends:
        text = (
            "👥 <b>Your Anonymous Friends List (0/{limit})</b>\n\n"
            "<i>You haven't added any anonymous friends yet!</i>\n"
            "While in a chat with someone you connect with, type /friendreq or tap "
            "<b>'Add to Anonymous Friends'</b> to stay connected without revealing your identity."
        ).format(limit=friend_limit)
    else:
        text = f"👥 <b>Your Anonymous Friends ({total_count}/{friend_limit})</b> — Page {page + 1}/{total_pages}\n<i>Tap any friend to view their card or connect!</i>\n"
        for f in page_friends:
            star = "⭐ " if f.get("is_favorite") else "💬 "
            name = f.get("custom_name", "Anonymous Friend")
            fid = f.get("friend_id")
            buttons.append([InlineKeyboardButton(f"{star}{name}", callback_data=f"fcard|{fid}|{page}")])

    # Pagination controls
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"flist|{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton("➡️ Next", callback_data=f"flist|{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    # 10th Line: Back to profile
    buttons.append([InlineKeyboardButton("🔙 Back to Profile", callback_data="profile_back")])
    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await safe_tele_func_call(update.callback_query.edit_message_text, text=text, parse_mode="HTML", reply_markup=markup)
    elif update.message:
        await safe_tele_func_call(update.message.reply_text, text=text, parse_mode="HTML", reply_markup=markup)


async def show_friend_card(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: int, page: int = 0):
    """Displays the individual friend card with manage/connect action buttons."""
    user_id = update.effective_user.id
    friend = await get_friend_card_db(user_id, friend_id)

    if not friend:
        if update.callback_query:
            await safe_tele_func_call(update.callback_query.answer, text="Friend not found.", show_alert=True)
            await show_friends_menu(update, context, page)
        return

    name = friend.get("custom_name", "Anonymous Friend")
    notes = friend.get("notes", "") or "<i>No notes added yet</i>"
    is_fav = friend.get("is_favorite", False)
    fav_icon = "⭐ " if is_fav else ""
    created_at = _format_date(friend.get("created_at"))

    # Determine status
    if is_in_chat(friend_id):
        status_str = "🔴 Currently in another chat"
    else:
        status_str = "🟢 Online / Available"

    card_text = (
        f"👤 <b>Anonymous Friend:</b> {fav_icon}<b>{name}</b>\n"
        f"📝 <b>Note:</b> {notes}\n"
        f"📅 <b>Friends since:</b> {created_at}\n"
        f"⚡ <b>Status:</b> {status_str}\n"
    )

    buttons = [
        [InlineKeyboardButton("💬 Connect & Chat", callback_data=f"fconn|{friend_id}|{page}")],
        [InlineKeyboardButton("⭐ Remove Favorite" if is_fav else "⭐ Set as Favorite", callback_data=f"ffav|{friend_id}|{page}")],
        [
            InlineKeyboardButton("✏️ Edit Name", callback_data=f"feditname|{friend_id}|{page}"),
            InlineKeyboardButton("📝 Edit Note", callback_data=f"feditnote|{friend_id}|{page}"),
        ],
        [InlineKeyboardButton("❌ Remove Friend", callback_data=f"frmconfirm|{friend_id}|{page}")],
        [InlineKeyboardButton("🔙 Back to Friends", callback_data=f"flist|{page}")],
    ]
    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await safe_tele_func_call(update.callback_query.edit_message_text, text=card_text, parse_mode="HTML", reply_markup=markup)


async def handle_friend_card_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Routes friend card buttons: favorite, edit name, edit note, remove, and connect."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    data = query.data or ""
    parts = data.split("|")
    action = parts[0]
    friend_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    if action == "flist":
        await show_friends_menu(update, context, page)
        return

    if action == "fcard":
        await show_friend_card(update, context, friend_id, page)
        return

    if action == "ffav":
        await toggle_friend_favorite_db(user_id, friend_id)
        await show_friend_card(update, context, friend_id, page)
        return

    if action == "frmconfirm":
        friend = await get_friend_card_db(user_id, friend_id)
        name = friend.get("custom_name", "this friend") if friend else "this friend"
        confirm_text = (
            f"⚠️ <b>Remove {name}?</b>\n\n"
            "This will remove the friendship for <b>both of you</b>. You won't be able to reconnect unless you meet again."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Yes, Remove", callback_data=f"frmdo|{friend_id}|{page}")],
            [InlineKeyboardButton("Cancel", callback_data=f"fcard|{friend_id}|{page}")],
        ])
        await safe_tele_func_call(query.edit_message_text, text=confirm_text, parse_mode="HTML", reply_markup=markup)
        return

    if action == "frmdo":
        await remove_friend_pair_db(user_id, friend_id)
        await safe_tele_func_call(
            query.edit_message_text,
            text="🗑️ <b>Friend removed from both lists.</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Friends", callback_data=f"flist|{page}")]])
        )
        return

    if action == "feditname":
        init.edit_stage[user_id] = f"friend_name|{friend_id}|{page}"
        await safe_tele_func_call(
            query.edit_message_text,
            text="✏️ <b>Enter new nickname for your friend:</b>\n<i>Send your reply as a text message below.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"fcard|{friend_id}|{page}")]])
        )
        return

    if action == "feditnote":
        init.edit_stage[user_id] = f"friend_note|{friend_id}|{page}"
        await safe_tele_func_call(
            query.edit_message_text,
            text="📝 <b>Enter a private note about this friend:</b>\n<i>Send your reply as a text message below.</i>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data=f"fcard|{friend_id}|{page}")]])
        )
        return

    if action == "fconn":
        await initiate_friend_connect(update, context, friend_id, page)
        return


async def initiate_friend_connect(update: Update, context: ContextTypes.DEFAULT_TYPE, friend_id: int, page: int = 0):
    """
    Connect flow:
    - If User A is in a chat: warn.
    - If Friend B is in a chat: notify A they're busy, send B an informational ping without buttons.
    - If Friend B is free: send B prompt with Accept/Decline (2-min timeout).
    """
    user_id = update.effective_user.id
    query = update.callback_query

    if is_in_chat(user_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>You are already in an active chat!</b>\nUse /stop or /next before connecting with a friend.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Friend Card", callback_data=f"fcard|{friend_id}|{page}")]])
        )
        return

    friend_a = await get_friend_card_db(user_id, friend_id)
    friend_b = await get_friend_card_db(friend_id, user_id)
    name_for_a = friend_a.get("custom_name", "Friend") if friend_a else "Friend"
    name_for_b = friend_b.get("custom_name", "Friend") if friend_b else "Friend"

    # Case 1: Friend B is currently in an active chat
    if is_in_chat(friend_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text=f"⏳ <b>Your friend {name_for_a} is currently in another chat!</b> Try again in a little while.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Friend Card", callback_data=f"fcard|{friend_id}|{page}")]])
        )
        # Informational ping to Friend B without buttons
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=friend_id,
            text=f"🔔 <b>Your friend {name_for_b} wants to chat with you!</b>",
            parse_mode="HTML",
        )
        return

    # Case 2: Friend B is free -> Send prompt with Accept/Decline
    conn_id = str(uuid.uuid4())[:8]
    init.pending_friend_connections[conn_id] = {
        "sender_id": user_id,
        "target_id": friend_id,
        "sender_name": name_for_a,
        "target_name": name_for_b,
        "created_at": time.time(),
    }

    req_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"f_c_acc|{conn_id}"),
            InlineKeyboardButton("❌ Decline", callback_data=f"f_c_dec|{conn_id}"),
        ]
    ])

    sent_msg = await safe_tele_func_call(
        context.bot.send_message,
        chat_id=friend_id,
        text=f"🔔 <b>Your friend {name_for_b} wants to chat with you!</b>",
        parse_mode="HTML",
        reply_markup=req_keyboard,
    )
    if sent_msg:
        init.pending_friend_connections[conn_id]["msg_id"] = sent_msg.message_id

    await safe_tele_func_call(
        query.edit_message_text,
        text=f"🔔 <b>Chat request sent to {name_for_a}!</b>\n<i>Waiting for them to respond (2 min)...</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Friend Card", callback_data=f"fcard|{friend_id}|{page}")]])
    )


async def handle_connect_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles Accept or Decline on friend connect requests."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    user_id = update.effective_user.id
    parts = (query.data or "").split("|")
    action = parts[0]
    conn_id = parts[1] if len(parts) > 1 else ""

    conn_data = init.pending_friend_connections.pop(conn_id, None)
    if not conn_data:
        await safe_tele_func_call(query.edit_message_text, text="<b>Chat request expired</b>", parse_mode="HTML")
        return

    sender_id = conn_data["sender_id"]
    target_id = conn_data["target_id"]
    name_for_sender = conn_data["sender_name"]
    name_for_target = conn_data["target_name"]

    if user_id != target_id:
        return

    if action == "f_c_dec":
        await safe_tele_func_call(query.edit_message_text, text="<b>Chat request rejected</b>", parse_mode="HTML")
        await safe_tele_func_call(
            context.bot.send_message,
            chat_id=sender_id,
            text=f"ℹ️ <b>Your friend {name_for_sender} is unavailable right now.</b>",
            parse_mode="HTML",
        )
        return

    # Check if sender has joined another chat in the meantime
    if is_in_chat(sender_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text="<b>Chat request expired</b>\n<i>Your friend entered another chat in the meantime.</i>",
            parse_mode="HTML"
        )
        return

    if is_in_chat(target_id):
        await safe_tele_func_call(
            query.edit_message_text,
            text="⚠️ <b>You are already in another chat!</b>",
            parse_mode="HTML"
        )
        return

    # Dequeue both from search queues
    await dequeue_user(sender_id)
    await dequeue_user(target_id)

    # Start chat with dedicated friend greeting
    success = await start_chat_session(
        context,
        sender_id,
        target_id,
        is_friend_connection=True,
        friend_name_1=name_for_sender,
        friend_name_2=name_for_target,
    )

    if success:
        await safe_tele_func_call(query.edit_message_text, text="<b>Chat request accepted</b>", parse_mode="HTML")
    else:
        await safe_tele_func_call(query.edit_message_text, text="⚠️ <b>Could not connect. Please try again.</b>", parse_mode="HTML")


async def handle_friend_input_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Intercepts user text input when editing a friend's nickname or note."""
    user_id = update.effective_user.id
    stage_info = init.edit_stage.get(user_id)
    if not stage_info or not stage_info.startswith("friend_"):
        return False

    parts = stage_info.split("|")
    stage_type = parts[0]
    friend_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

    init.edit_stage.pop(user_id, None)
    new_text = (update.message.text or "").strip()

    if stage_type == "friend_name":
        if not new_text or len(new_text) > 40:
            await safe_tele_func_call(
                update.message.reply_text,
                text="⚠️ Nickname must be between 1 and 40 characters.",
                parse_mode="HTML"
            )
            return True
        await update_friend_nickname_db(user_id, friend_id, new_text)
        await safe_tele_func_call(
            update.message.reply_text,
            text=f"✅ <b>Nickname updated to '{new_text}'!</b>",
            parse_mode="HTML"
        )
        await show_friend_card(update, context, friend_id, page)
        return True

    elif stage_type == "friend_note":
        if len(new_text) > 300:
            await safe_tele_func_call(
                update.message.reply_text,
                text="⚠️ Note must be under 300 characters.",
                parse_mode="HTML"
            )
            return True
        await update_friend_note_db(user_id, friend_id, new_text)
        await safe_tele_func_call(
            update.message.reply_text,
            text="✅ <b>Friend note updated!</b>",
            parse_mode="HTML"
        )
        await show_friend_card(update, context, friend_id, page)
        return True

    return False
