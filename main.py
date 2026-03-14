# Imports everything needed from telegram module
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler

# Imports everything needed from user-defined modules responsible for basic working of the bot
from saveNload import save_user_data, load_user_data
from app import home, run, keep_alive
from relay import relay_message

# Imports everything needed from the user-defined command module
from commands.start import start
from commands.find import find
from commands.next import next
from commands.stop import stop
from commands.help import help_command
from commands.profile import show_profile

# Imports everything needed from the user-defined handler module to handle the command inputs of the users
from handlers.rating import handle_vote
from handlers.gender import handle_gender_selection
from handlers.country import handle_country_selection
from handlers.edit import handle_edit_selection

from security import global_error_handler

# Imports for basic functionality of bot and its data credentials
import asyncio
import init


# Function to preset the commands available in the bot
async def set_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),  # start
        BotCommand("find", "Find a new chat partner"),  # find
        BotCommand("next", "Skip your current partner"),  # next
        BotCommand("stop", "Stop the current chat"),  # stop
        BotCommand("help", "Show help"),  # help
        BotCommand("profile", "Show user profile"),  # profile
    ]
    await application.bot.set_my_commands(commands)  # To set the commands to the bot menu


# Function to save the user data periodically every minute
async def periodic_save(context):
    save_user_data(init.user_details, init.dirty_users)


# Function to free the feedback_track to handle clean voting system while minimising data overflow
async def periodic_feedback_clear(context):
    for user_id, details in init.user_details.items():
        if details.get("feedback_track"):
            details["feedback_track"] = {}
            init.dirty_users.add(user_id)


async def on_shutdown(application):
    print("⚠️ Bot shutting down. Saving user data...")
    try:
        save_user_data(init.user_details, init.dirty_users)
    except Exception as e:
        print("Failed to save during shutdown:", e)


async def on_startup(application):
    application.job_queue.run_repeating(periodic_save, interval=60, first=60)  # Saves the user data
    application.job_queue.run_repeating(periodic_feedback_clear, interval=28800, first=28800)  # Frees up the feedback_track


# Main function to keep the bot alive, handle user commands and user inputs, relaying messages between users
def main():
    keep_alive()  # Keeps the bot alive

    app = (
        ApplicationBuilder()
        .token(init.BOT_TOKEN)
        .post_init(set_commands)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )  # The app which makes the bot work

    app.add_handler(CommandHandler("start", start))  # Connects the 'start' command to its functionality
    app.add_handler(CommandHandler("find", find))  # Connects the 'find' command to its functionality
    app.add_handler(CommandHandler("next", next))  # Connects the 'next' command to its functionality
    app.add_handler(CommandHandler("stop", stop))  # Connects the 'stop' command to its functionality
    app.add_handler(CommandHandler("help", help_command))  # Connects the 'help' command to its functionality
    app.add_handler(CommandHandler("profile", show_profile))  # Connects the 'profile' command to its functionality
    app.add_handler(CallbackQueryHandler(handle_vote, pattern="rate\\|\\d+\\|(up|down)$"))  # Handles the voting mechanics
    app.add_handler(CallbackQueryHandler(handle_gender_selection, pattern="^gender\\|[MF]$"))  # Handles the selection of gender from the user
    app.add_handler(CallbackQueryHandler(handle_country_selection, pattern="^country\\|.+$"))  # Handles the selection of country from the user
    app.add_handler(CallbackQueryHandler(handle_vote, pattern="^report\\|\\d+$"))  # Handles the reporting mechanics
    app.add_handler(CallbackQueryHandler(handle_edit_selection, pattern="^edit\\|.+$"))  # Handles the selection of what to edit from the user
    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Sticker.ALL | filters.PHOTO | filters.VIDEO |
         filters.VIDEO_NOTE | filters.AUDIO | filters.Document.ALL | filters.VOICE) & ~filters.COMMAND,
        relay_message
    ))  # filters the commands from the messages sent by the user

    app.add_error_handler(global_error_handler)

    app.run_polling(drop_pending_updates=True)  # Runs the app


# Part which keeps the event loop running
if __name__ == '__main__':
    main()
