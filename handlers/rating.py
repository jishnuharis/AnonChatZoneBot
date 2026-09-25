from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from telegram.ext import ContextTypes

from security import safe_tele_func_call
from moderation import REPORT_REASONS, file_report
from saveNload import record_user_rating, add_user_block, get_user_votes, can_user_block
from message import RATE_PROMPT_TEXT, REPORT_REASON_PROMPT_TEXT, REPORT_LOGGED_TEXT

import init
import referral


def _feedback_keyboard(to_id: int, can_vote: bool = True, can_block: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if can_vote:
        buttons.append([
            InlineKeyboardButton("👍", callback_data=f"rate|{to_id}|up"),
            InlineKeyboardButton("👎", callback_data=f"rate|{to_id}|down")
        ])

    action_row = [InlineKeyboardButton("🚩 Report", callback_data=f"report|{to_id}")]
    if can_block:
        action_row.append(InlineKeyboardButton("🚫 Block", callback_data=f"rateblock|{to_id}"))
    buttons.append(action_row)

    return InlineKeyboardMarkup(buttons)


async def ask_for_rating(bot, from_id: int, to_id: int):
    markup = _feedback_keyboard(to_id, can_vote=True, can_block=True)
    await safe_tele_func_call(
        bot.send_message,
        chat_id=from_id,
        text=RATE_PROMPT_TEXT,
        reply_markup=markup,
        parse_mode="HTML"
    )
    await referral.maybe_announce(bot, from_id)


async def handle_vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query: CallbackQuery = update.callback_query
    data = query.data.split("|")
    if not (2 <= len(data) <= 3):
        await query.answer()
        return

    action = data[0]
    target_id = int(data[1])

    if action == "rate":
        vote_type = data[2]
        emoji = "👍" if vote_type == "up" else "👎"
        await safe_tele_func_call(query.answer, f"Thanks for your feedback! {emoji}")

        # Ensure target user data is loaded without inserting blank stubs
        if target_id not in init.user_details:
            await init.ensure_user_loaded(target_id)

        # Record in DB and refresh live vote counts
        await record_user_rating(user_id, target_id, vote_type)
        updated_votes = await get_user_votes(target_id)
        if target_id in init.user_details:
            init.user_details[target_id]["votes"] = updated_votes

        # Update keyboard on message to remove vote buttons, allowing report or block
        markup = _feedback_keyboard(target_id, can_vote=False, can_block=True)
        await safe_tele_func_call(query.edit_message_reply_markup, reply_markup=markup)
        return

    if action == "rateblock":
        allowed, count, limit = await can_user_block(user_id, target_id)
        if not allowed:
            if limit == 3:
                alert = "⚠️ Block limit reached (3/3)! Free accounts can have up to 3 active blocks. Upgrade with /subscribe for up to 32 blocks."
            else:
                alert = "⚠️ Block limit reached (32/32)! You have reached the maximum limit of 32 active blocks."
            await safe_tele_func_call(query.answer, alert, show_alert=True)
            return

        await query.answer()
        confirm_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚫 Yes, Block User", callback_data=f"rateblock_confirm|{target_id}"),
                InlineKeyboardButton("« Cancel", callback_data=f"rateblock_cancel|{target_id}"),
            ]
        ])
        await safe_tele_func_call(
            query.edit_message_text,
            text=(
                f"⚠️ <b>Are you sure you want to block this user?</b>\n"
                f"Neither of you will match with each other for the next 24 hours.\n"
                f"Active blocks: <b>{count}/{limit}</b>"
            ),
            reply_markup=confirm_markup,
            parse_mode="HTML"
        )
        return

    if action == "rateblock_confirm":
        allowed, count, limit = await can_user_block(user_id, target_id)
        if not allowed:
            if limit == 3:
                alert = "⚠️ Block limit reached (3/3)! Free accounts can have up to 3 active blocks. Upgrade with /subscribe for up to 32 blocks."
            else:
                alert = "⚠️ Block limit reached (32/32)! You have reached the maximum limit of 32 active blocks."
            await safe_tele_func_call(query.answer, alert, show_alert=True)
            return

        await add_user_block(user_id, target_id)
        await safe_tele_func_call(query.answer, "🚫 User blocked! You will not match with them for the next 24 hours.", show_alert=True)
        await safe_tele_func_call(
            query.edit_message_text,
            text="🚫 <b>User blocked.</b> You will not be paired with them for the next 24 hours.",
            reply_markup=None,
            parse_mode="HTML"
        )
        return

    if action == "rateblock_cancel":
        await query.answer()
        markup = _feedback_keyboard(target_id, can_vote=False, can_block=True)
        await safe_tele_func_call(
            query.edit_message_text,
            text=RATE_PROMPT_TEXT,
            reply_markup=markup,
            parse_mode="HTML"
        )
        return

    if action == "report":
        await query.answer()
        buttons = [[InlineKeyboardButton(label, callback_data=f"reportreason|{target_id}|{code}")]
                   for code, (label, _weight) in REPORT_REASONS.items()]
        buttons.append([InlineKeyboardButton("« Back", callback_data=f"reportback|{target_id}")])
        await safe_tele_func_call(
            query.edit_message_text,
            text=REPORT_REASON_PROMPT_TEXT,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode="HTML"
        )
        return


async def handle_report_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split("|")[1])
    markup = _feedback_keyboard(target_id, can_vote=False, can_block=True)
    await safe_tele_func_call(
        query.edit_message_text,
        text=RATE_PROMPT_TEXT,
        reply_markup=markup,
        parse_mode="HTML"
    )


async def handle_report_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🚩 Report submitted.")
    user_id = update.effective_user.id
    _, target_id, code = query.data.split("|")
    target_id = int(target_id)

    await file_report(user_id, target_id, code, context=context)
    init.dirty_users.update([user_id, target_id])

    await safe_tele_func_call(
        query.edit_message_text,
        text=REPORT_LOGGED_TEXT,
        reply_markup=None,
        parse_mode="HTML"
    )
