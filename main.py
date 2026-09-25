import os
import logging
from telegram import BotCommand, Update, BotCommandScopeChat
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler,
    TypeHandler, MessageReactionHandler, PreCheckoutQueryHandler,
)

from saveNload import save_user_data, init_pool, close_pool
from app import keep_alive
from relay import relay_message, relay_reaction, relay_edited_message

from commands.start import start
from commands.find import find
from commands.next import skip_partner, handle_undo_skip
from commands.stop import stop
from commands.block import block_command, handle_block_callback
from commands.nudge import handle_nudge, status_command
from commands.cancel import cancel
from commands.help import help_command
from commands.profile import show_profile, handle_profile_back
from commands.call import call_command, handle_call_response
from handlers.friends import (
    send_friend_request, show_friends_menu, handle_friend_request_response,
    handle_friend_card_actions, handle_connect_response
)
from handlers.transcript import handle_export_transcript
from commands.games import games_menu, handle_games_menu_selection
from commands.admin_commands import (
    broadcast, connect, ban_user, unban_user, check_user,
    giveaway_subscription, referral_scheme_command, admin_stats, queue_stats, campaign_command
)
from commands.subscribe import show_subscribe_menu, handle_tier_selection
from commands.top import show_top_leaderboard, handle_top_callback
from commands.gift import gift_command, handle_gift_callback
from handlers.payments import handle_pre_checkout, handle_successful_payment
from referral import handle_referral_link_button

from handlers.rating import handle_vote, handle_report_reason, handle_report_back
from handlers.gender import handle_gender_selection
from handlers.country import handle_country_selection
from handlers.edit import handle_edit_selection
from handlers.preferences import handle_preferences_selection
from channel_gate import handle_check_channel_status, handle_start_find_callback

from games.game_requests import send_request, handle_game_request_response
import games.coin_steal as coin_steal
import games.tictactoe as tictactoe
import games.rps as rps
import games.guess_it as guess_it
import games.would_you_rather as would_you_rather
import games.trivia as trivia

from media_privacy import handle_private_command, handle_view_once, sweep_expired_media

from security import global_error_handler, restriction_gate
from moderation import decay_severity_scores

import init

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Silence noisy background libraries so console logs remain clean and focused
for _noisy in (
    "httpx", "httpcore", "apscheduler", "apscheduler.scheduler",
    "apscheduler.executors.default", "telegram", "telegram.ext",
    "telegram.ext.Application", "werkzeug"
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


async def set_commands(application):
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("find", "Find a new chat partner"),
        BotCommand("next", "Skip your current partner"),
        BotCommand("stop", "Stop the current chat"),
        BotCommand("block", "Block current partner"),
        BotCommand("nudge", "Nudge your chat partner"),
        BotCommand("status", "Check partner connection & activity status"),
        BotCommand("cancel", "Cancel ongoing game or request"),
        BotCommand("help", "Show help"),
        BotCommand("profile", "Show user profile"),
        BotCommand("friendreq", "Add current partner to anonymous friends"),
        BotCommand("friends", "Manage anonymous friends list"),
        BotCommand("call", "Start anonymous voice call with partner"),
        BotCommand("games", "Play a mini-game with partner"),
        BotCommand("private", "Arm Privacy Mode for next media"),
        BotCommand("subscribe", "View/purchase subscription"),
        BotCommand("top", "Show weekly leaderboard"),
        BotCommand("gift", "Send a gift to your chat partner"),
    ]
    await application.bot.set_my_commands(commands)

    admin_commands = commands + [
        BotCommand("stats", "Bot user and performance statistics"),
        BotCommand("queue", "Queue and matchmaking status"),
        BotCommand("connect", "Connect directly to a user ID"),
        BotCommand("checkuser", "Check user status and reports"),
        BotCommand("ban", "Ban or restrict a user"),
        BotCommand("unban", "Lift restriction on a user"),
        BotCommand("giveaway", "Give free subscription to user"),
        BotCommand("referral", "Configure referral promo"),
        BotCommand("broadcast", "Send message to users"),
        BotCommand("campaign", "Manage sponsor campaigns"),
    ]
    admin_ids = set(init.ADMIN_IDS)
    if init.OWNER and str(init.OWNER).isdigit():
        admin_ids.add(int(init.OWNER))

    for admin_id in admin_ids:
        try:
            await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logger.debug(f"Notice setting admin commands for {admin_id}: {e}")


async def periodic_save(context):
    await save_user_data(init.user_details, init.dirty_users)


async def periodic_severity_decay(context):
    await decay_severity_scores()


async def periodic_queue_sweep(context):
    from matchmaking import queue_sweep
    await queue_sweep(context)


async def periodic_media_sweep(context):
    await sweep_expired_media(context)


async def on_shutdown(application):
    print("⚠️ Bot shutting down. Saving user data...")
    try:
        await save_user_data(init.user_details, init.dirty_users)
    except Exception as e:
        print("Failed to save during shutdown:", e)
    finally:
        await close_pool()


async def on_startup(application):
    # Open the DB pool and load persisted data before polling starts.
    await init_pool()
    await init.load_all()

    application.job_queue.run_repeating(periodic_save, interval=60, first=60)
    application.job_queue.run_repeating(periodic_severity_decay, interval=86400, first=3600)
    application.job_queue.run_repeating(periodic_queue_sweep, interval=5, first=5)
    application.job_queue.run_repeating(periodic_media_sweep, interval=3600, first=3600)

    active_chats_count = len(init.active_pairs) // 2
    users_count = len(init.user_details)
    print(f"🚀 Bot is active. {users_count} active users, {active_chats_count} active chats.", flush=True)
    logger.info(f"🚀 Bot is active. {users_count} active users, {active_chats_count} active chats.")


async def post_init_tasks(application):
    await set_commands(application)
    await on_startup(application)


def main():
    keep_alive()

    builder = (
        ApplicationBuilder()
        .token(init.BOT_TOKEN)
        .post_init(post_init_tasks)
        .post_shutdown(on_shutdown)
    )

    # Media Outbound Throughput Upgrade:
    # If a self-hosted local Bot API server is configured (e.g. http://localhost:8081/bot),
    # configure local base_url to enable 2,000 MB file sizes, local network speed, and higher rate limits!
    local_api_url = os.getenv("LOCAL_BOT_API_URL")
    if local_api_url:
        builder = builder.base_url(local_api_url)
        logging.getLogger(__name__).info(f"Using Local Telegram Bot API Server: {local_api_url}")

    app = builder.build()

    app.add_handler(TypeHandler(Update, restriction_gate), group=-2)

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("find", find))
    app.add_handler(CommandHandler("next", skip_partner))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("block", block_command))
    app.add_handler(CommandHandler("nudge", handle_nudge))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CommandHandler("friendreq", send_friend_request))
    app.add_handler(CommandHandler("friends", lambda u, c: show_friends_menu(u, c, 0)))
    app.add_handler(CommandHandler("call", call_command))
    app.add_handler(CommandHandler("games", games_menu))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(MessageHandler(filters.CaptionRegex(r"^/broadcast(?:@\w+)?(?:\s|$)"), broadcast))
    app.add_handler(CommandHandler("connect", connect))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("checkuser", check_user))
    app.add_handler(CommandHandler("private", handle_private_command))
    app.add_handler(CommandHandler("subscribe", show_subscribe_menu))
    app.add_handler(CommandHandler("top", show_top_leaderboard))
    app.add_handler(CommandHandler("leaderboard", show_top_leaderboard))
    app.add_handler(CommandHandler("gift", gift_command))
    app.add_handler(CommandHandler("giveaway", giveaway_subscription))
    app.add_handler(CommandHandler("referral", referral_scheme_command))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("queue", queue_stats))
    app.add_handler(CommandHandler("campaign", campaign_command))
    app.add_handler(MessageHandler(filters.CaptionRegex(r"^/campaign(?:@\w+)?(?:\s|$)"), campaign_command))

    app.add_handler(CallbackQueryHandler(handle_check_channel_status, pattern=r"^check_channel_status$"))
    app.add_handler(CallbackQueryHandler(handle_start_find_callback, pattern=r"^start_find_callback$"))

    app.add_handler(CallbackQueryHandler(handle_top_callback, pattern=r"^top\|\w+$"))
    app.add_handler(CallbackQueryHandler(handle_gift_callback, pattern=r"^gift\|\w+$"))
    app.add_handler(CallbackQueryHandler(handle_tier_selection, pattern=r"^sub\|\w+$"))
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))

    app.add_handler(CallbackQueryHandler(handle_undo_skip, pattern=r"^undoskip\|\d+$"))
    app.add_handler(CallbackQueryHandler(handle_friend_request_response, pattern=r"^freq_(acc|dec)\|\w+$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: send_friend_request(u, c, target_id=int(u.callback_query.data.split("|")[1])), pattern=r"^friendreq_end\|\d+$"))
    app.add_handler(CallbackQueryHandler(handle_friend_card_actions, pattern=r"^(flist|fcard|ffav|feditname|feditnote|frmconfirm|frmdo|fconn)\|\d+(?:\|\d+)?$"))
    app.add_handler(CallbackQueryHandler(handle_connect_response, pattern=r"^f_c_(acc|dec)\|\w+$"))
    app.add_handler(CallbackQueryHandler(handle_profile_back, pattern=r"^profile_back$"))
    app.add_handler(CallbackQueryHandler(handle_export_transcript, pattern=r"^export_chat\|.+$"))
    app.add_handler(CallbackQueryHandler(handle_call_response, pattern=r"^call_(acc|dec|end)\|.+$"))

    app.add_handler(CallbackQueryHandler(handle_block_callback, pattern=r"^(block_confirm|block_cancel)(?:\|\d+\|(?:active|recent))?$"))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern=r"^rate\|\d+\|(up|down)$"))
    app.add_handler(CallbackQueryHandler(handle_vote, pattern=r"^(rateblock|rateblock_confirm|rateblock_cancel)\|\d+$"))
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
    app.add_handler(CallbackQueryHandler(trivia.handle_callback, pattern=r"^trivia\|\d+$"))

    app.add_handler(CallbackQueryHandler(handle_view_once, pattern=r"^viewonce\|.+$"))

    app.add_handler(MessageHandler(
        (filters.TEXT | filters.Sticker.ALL | filters.PHOTO | filters.VIDEO |
         filters.VIDEO_NOTE | filters.AUDIO | filters.Document.ALL | filters.VOICE | filters.ANIMATION | filters.Dice.ALL) & ~filters.COMMAND,
        relay_message
    ))

    app.add_handler(MessageHandler(
        filters.UpdateType.EDITED_MESSAGE & ~filters.COMMAND,
        relay_edited_message
    ))

    app.add_handler(MessageReactionHandler(relay_reaction))

    app.add_error_handler(global_error_handler)

    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
