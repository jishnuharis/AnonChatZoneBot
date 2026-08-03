from telegram import BotCommand, Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler,
    TypeHandler, MessageReactionHandler, PreCheckoutQueryHandler,
)

from saveNload import save_user_data
from app import keep_alive
from relay import relay_message, relay_reaction

from commands.start import start
from commands.find import find
from commands.next import skip_partner
from commands.stop import stop
from commands.cancel import cancel
from commands.help import help_command
from commands.profile import show_profile
from commands.games import games_menu, handle_games_menu_selection
from commands.admin_commands import broadcast, connect, ban_user, unban_user, check_user, giveaway_subscription, referral_scheme_command
from commands.subscribe import show_subscribe_menu, handle_tier_selection
from handlers.payments import handle_pre_checkout, handle_successful_payment
from referral import handle_referral_link_button

from handlers.rating import handle_vote, handle_report_reason, handle_report_back
from handlers.gender import handle_gender_selection
from handlers.country import handle_country_selection
from handlers.edit import handle_edit_selection
from handlers.preferences import handle_preferences_selection

from games.game_requests import send_request, handle_game_request_response
import games.coin_steal as coin_steal
import games.tictactoe as tictactoe
import games.rps as rps
import games.guess_it as guess_it
import games.would_you_rather as would_you_rather

from media_privacy import handle_private_command, handle_view_once, sweep_expired_media

from security import global_error_handler, restriction_gate
from moderation import decay_severity_scores

import init


async def set_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("find", "Find a new chat partner"),
        BotCommand("next", "Skip your current partner"),
        BotCommand("stop", "Stop the current chat"),
        BotCommand("cancel", "Cancel your ongoing game"),
        BotCommand("help", "Show help"),
        BotCommand("profile", "Show user profile"),
        BotCommand("games", "Play a mini-game with your partner"),
        BotCommand("private", "Arm Privacy Mode for your next media"),
        BotCommand("subscribe", "View/purchase a subscription plan"),
    ]
    await application.bot.set_my_commands(commands)


async def periodic_save(context):
    save_user_data(init.user_details, init.dirty_users)


async def periodic_feedback_clear(context):
    for user_id, details in init.user_details.items():
        if details.get("feedback_track"):
            details["feedback_track"] = {}
            init.dirty_users.add(user_id)


async def periodic_severity_decay(context):
    decay_severity_scores()


async def periodic_queue_sweep(context):
    from matchmaking import queue_sweep
    await queue_sweep(context)


async def periodic_media_sweep(context):
    await sweep_expired_media(context)


async def on_shutdown(application):
    print("⚠️ Bot shutting down. Saving user data...")
    try:
        save_user_data(init.user_details, init.dirty_users)
    except Exception as e:
        print("Failed to save during shutdown:", e)


async def on_startup(application):
    application.job_queue.run_repeating(periodic_save, interval=60, first=60)
    application.job_queue.run_repeating(periodic_feedback_clear, interval=28800, first=28800)
    application.job_queue.run_repeating(periodic_severity_decay, interval=86400, first=3600)
    application.job_queue.run_repeating(periodic_queue_sweep, interval=5, first=5)
    application.job_queue.run_repeating(periodic_media_sweep, interval=3600, first=3600)


async def post_init_tasks(application):
    await set_commands(application)
    await on_startup(application)


def main():
    keep_alive()

    app = (
        ApplicationBuilder()
        .token(init.BOT_TOKEN)
        .post_init(post_init_tasks)
        .post_shutdown(on_shutdown)
        .build()
    )

    app.add_handler(TypeHandler(Update, restriction_gate), group=-2)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("next", skip_partner))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("games", games_menu))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("checkuser", check_user))
    app.add_handler(CommandHandler("private", handle_private_command))
    app.add_handler(CommandHandler("subscribe", show_subscribe_menu))
    app.add_handler(CommandHandler("giveaway", giveaway_subscription))
    app.add_handler(CommandHandler("referral", referral_scheme_command))

    app.add_handler(CallbackQueryHandler(handle_tier_selection, pattern=r"^sub\|\w+$"))
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    app.add_handler(CallbackQueryHandler(handle_vote, pattern=r"^rate\|\d+\|(up|down)$"))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern=r"^report\|\d+$"))
    app.add_handler(CallbackQueryHandler(handle_report_reason, pattern=r"^reportreason\|\d+\|\w+$"))
    app.add_handler(CallbackQueryHandler(handle_report_back, pattern=r"^reportback\|\d+$"))
    app.add_handler(CallbackQueryHandler(handle_gender_selection, pattern=r"^gender\|[MF]$"))
    app.add_handler(CallbackQueryHandler(handle_country_selection, pattern=r"^country\|.+$"))
    app.add_handler(CallbackQueryHandler(handle_edit_selection, pattern=r"^edit\|.+$"))
    app.add_handler(CallbackQueryHandler(handle_preferences_selection, pattern=r"^pref\|.+$"))
    app.add_handler(CallbackQueryHandler(handle_referral_link_button, pattern=r"^refgen$"))

    # Games
    app.add_handler(CallbackQueryHandler(handle_games_menu_selection, pattern=r"^gamemenu\|\w+$"))
    app.add_handler(CallbackQueryHandler(handle_game_request_response, pattern=r"^gamereq\|(accept|decline)$"))
    app.add_handler(CallbackQueryHandler(coin_steal.handle_callback, pattern=r"^cs\|(save|steal)$"))
    app.add_handler(CallbackQueryHandler(tictactoe.handle_callback, pattern=r"^ttt\|.+$"))
    app.add_handler(CallbackQueryHandler(rps.handle_callback, pattern=r"^rps\|(rock|paper|scissors)$"))
    app.add_handler(CallbackQueryHandler(guess_it.handle_callback, pattern=r"^gi\|.+$"))
    app.add_handler(CallbackQueryHandler(would_you_rather.handle_callback, pattern=r"^wyr\|[AB]$"))

    app.add_handler(CallbackQueryHandler(handle_view_once, pattern=r"^viewonce\|.+$"))

    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Sticker.ALL | filters.PHOTO | filters.VIDEO |
         filters.VIDEO_NOTE | filters.AUDIO | filters.Document.ALL | filters.VOICE | filters.ANIMATION) & ~filters.COMMAND,
        relay_message
    ))

    app.add_handler(MessageReactionHandler(relay_reaction))

    app.add_error_handler(global_error_handler)

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
