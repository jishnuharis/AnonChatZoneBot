import logging
from typing import Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import init
from security import safe_tele_func_call

logger = logging.getLogger(__name__)

GROUP_REDIRECT_TEXT = (
    "⚠️ <b>This command cannot be used inside groups!</b>\n\n"
    "<i>Please open a private chat with the bot to use this feature.</i>"
)


def is_group_chat(update: Update) -> bool:
    """Checks if the update originates from a group or supergroup."""
    chat = update.effective_chat
    return bool(chat and chat.type in ("group", "supergroup"))


def get_group_redirect_keyboard(bot_username: str, start_arg: str = "group") -> InlineKeyboardMarkup:
    """Returns an inline button redirecting the user to the bot's private DM."""
    url = f"https://t.me/{bot_username}?start={start_arg}" if bot_username else "https://t.me"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Open Bot", url=url)]
    ])


async def reply_group_redirect(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    start_arg: str = "group",
    custom_text: Optional[str] = None
):
    """Replies to the triggering command message with a redirect notice and button."""
    bot_username = context.bot.username if hasattr(context, "bot") and context.bot else ""
    text = custom_text or GROUP_REDIRECT_TEXT
    reply_markup = get_group_redirect_keyboard(bot_username, start_arg)
    
    if update.effective_message:
        await safe_tele_func_call(
            update.effective_message.reply_text,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


async def delete_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Deletes the admin's command message inside a group to keep admin commands confidential.
    Returns True if deleted, False otherwise.
    """
    if not is_group_chat(update) or not update.effective_message:
        return False
    try:
        await update.effective_message.delete()
        return True
    except (BadRequest, Forbidden) as e:
        logger.debug(f"Could not delete admin command message: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected error deleting admin command: {e}")
        return False


async def is_group_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    """
    Checks if user_id is a group administrator/creator in chat_id,
    or a global bot admin in init.ADMIN_IDS / init.OWNER.
    """
    from moderation import is_admin
    if is_admin(user_id):
        return True

    try:
        member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        return member.status in ("administrator", "creator")
    except Exception as e:
        logger.debug(f"Error checking group admin status for user {user_id} in {chat_id}: {e}")
        return False


async def resolve_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    arg_index: int = 0
) -> Optional[Tuple[int, Optional[str]]]:
    """
    Resolves target user (user_id, username/display_name) from either:
    1. Reply-to message (update.message.reply_to_message.from_user)
    2. Command argument at arg_index (@username or numeric user_id)
    """
    msg = update.effective_message
    if not msg:
        return None

    # 1. Target from reply
    cand = getattr(msg, "reply_to_message", None)
    if cand and getattr(cand, "from_user", None) and isinstance(getattr(cand.from_user, "id", None), int):
        target_user = cand.from_user
        username = getattr(target_user, "username", None)
        if username:
            init.username_to_id[username.lower()] = target_user.id
        return target_user.id, (f"@{username}" if username else getattr(target_user, "first_name", f"User {target_user.id}"))

    # 2. Target from argument
    args = getattr(context, "args", None) or []
    if len(args) > arg_index:
        arg_val = str(args[arg_index]).strip()
        if arg_val.startswith("@"):
            clean_username = arg_val[1:].lower()
            target_id = init.username_to_id.get(clean_username)
            if not target_id:
                # Search cached user_details
                for uid, udata in init.user_details.items():
                    if udata.get("username", "").lower() == clean_username:
                        target_id = uid
                        init.username_to_id[clean_username] = uid
                        break
            if target_id:
                return target_id, arg_val
            return None, arg_val  # Username given but not found yet
        elif arg_val.isdigit():
            target_id = int(arg_val)
            return target_id, f"User {target_id}"

    return None
