from telegram.error import Forbidden, Conflict, BadRequest  # Importing the 'Forbidden' exception
from telegram.helpers import escape_markdown

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

        tb_list = traceback.extract_tb(e.__traceback__)

        text = f" _🚨 YO THERE IS AN ERROR TWIN 🚨_\n\n"
        text += f"_{type(e).__name__}:_ {e}\n\n"

        if update and update.effective_user:
            text += f"\n_👤 User ID:_ {update.effective_user.id}\n\n"

        for frame in reversed(tb_list):
            if "site-packages" not in frame.filename:
                file = frame.filename
                line = frame.lineno
                func = frame.name
                code = frame.line or "No source available"

                safe_code = escape_markdown(code or "None", version=2)
                safe_file = escape_markdown(file, version=2)
                safe_func = escape_markdown(func, version=2)

                text += (
                    f"🚨 _Error in_ *{safe_file}*: *{line}*\n"
                    f"⚙️ _Function:_ *{safe_func}*\n"
                    f"💻 _Code:_ `{safe_code}`"
                )
                break
        # text += f"_📍 Traceback:_\n```{tb}```"

        await context.bot.send_message(chat_id=init.OWNER, text=text, parse_mode="MarkdownV2")
    except Exception as err:
        print("Error inside the error handler: ", err)
