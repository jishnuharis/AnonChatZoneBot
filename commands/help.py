# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call


# Function which helps the user by telling them how different commands work
@check_user_profile
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_tele_func_call(update.message.reply_text, text="""
🤖 *Chat Zone - Anonymous Chat Bot*

_You can connect with people and chat anonymously in Telegram_
    
_This bot can send texts, stickers, photos, videos, gifs, voice and video notes_

*Commands:*
/start _- Show welcome message_
/find _- Find a new partner_
/next _- Skip the current chat_
/stop _- Stop the current chat_
/help _- Show help_
/profile _- Show user profile_
/coinsteal _-Play a game of Coin Steal_

_If you have any feature suggestions or ideas feel free to join our group_ t.me/groupchatzone _and let us know_
""", parse_mode="Markdown")
