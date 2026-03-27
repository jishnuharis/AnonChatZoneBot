from telegram.error import Forbidden, Conflict, BadRequest  # Importing the 'Forbidden' exception

import traceback

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
        if isinstance(e, BadRequest) and "message is not modified" in str(e).lower():
            return

        tb = "".join(traceback.format_exception(None, e, e.__traceback__))

        text = f" 🚨 YO THERE IS AN ERROR TWIN 🚨 \n\n"
        text += f"{type(e).__name__}: {e}\n\n"

        if update and update.effective_user:
            text += f"\n👤 User ID: {update.effective_user.id}\n\n"

        text += f"📍 Traceback:\n{tb}"

        await context.bot.send_message(chat_id=init.OWNER, text=text[:4000])
    except Exception as err:
        print("Error inside the error handler: ", err)
