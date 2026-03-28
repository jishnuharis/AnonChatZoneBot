# Imports everything needed from the telegram module
from telegram import Update
from telegram.ext import ContextTypes

from handlers.setup import check_user_profile  # Imports the handler which checks if the user's profile exists
from security import safe_tele_func_call


# Function which helps the user by telling them how different commands work
@check_user_profile
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_tele_func_call(update.message.reply_text, text="""
🤖 *Anonymous Chat Bot*
_Commands:_
/start _- Show welcome message_
/find _- Find a new partner_
/next _- Skip current chat_
/stop _- Stop current chat_
/help _- Show this message_
/profile _- Show user profile_
""", parse_mode="Markdown")
