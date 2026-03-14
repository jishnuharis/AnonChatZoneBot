from telegram.error import Forbidden, Conflict  # Importing the 'Forbidden' exception

import init


# Function which checks if the bot is blocked by the given user
async def safe_tele_func_call(caller, *args, **kwargs):
    try:  # Tries to send a typing action to the user to check if it is blocked by the user
        return await caller(*args, **kwargs)
    except Forbidden:
        return None


async def global_error_handler(update, context):
    try:
        e = context.error

        if isinstance(e, Conflict):
            return

        text = f" 🚨 YO THERE IS AN ERROR TWIN 🚨 \n\n{type(e).__name__}: {e}\n"
        if update and update.effective_user:
            text += f"\n👤 User ID: {update.effective_user.id}"
        text += "\n\nngl something just exploded 😭 pls come check...!"

        await context.bot.send_message(chat_id=init.OWNER, text=text)
    except:
        pass
