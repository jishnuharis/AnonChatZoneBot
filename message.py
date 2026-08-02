# Holds every constant, non-dynamic user-facing text used across the bot.
# Anything built with an f-string (i.e. contains data that changes per-call)
# stays inline at its call site - only fully-static text lives here.

# ---------------------------------------------------------------------------
# commands/start.py
# ---------------------------------------------------------------------------
WELCOME_BACK_TEXT = "👋 <i>Welcome back to</i> <b>Chat Zone - Anonymous Chat Bot!</b>\n<i>Use</i> /find <i>to look for a partner.</i>"

# ---------------------------------------------------------------------------
# commands/find.py
# ---------------------------------------------------------------------------
ALREADY_IN_CHAT_TEXT = "⚠️ <b>You're already in a chat.</b>\n<i>Use</i> /stop <i>or</i> /next <i>first.</i>"
LOOKING_FOR_PARTNER_TEXT = "🔍 <b>Looking for a partner...</b>\n<i>Matching you with someone who shares your interests if possible.</i>"

# ---------------------------------------------------------------------------
# commands/next.py
# ---------------------------------------------------------------------------
PARTNER_LEFT_CHAT_TEXT = "⛔ <b>Your partner left the chat.</b>"
PARTNER_SKIPPED_TEXT = "🔁 <b>Partner skipped...</b>\n<i>You're added to the waiting queue, finding a new one...</i>"
NOT_IN_CHAT_USE_FIND_TEXT = "❗ <b>You're not in a chat.</b>\n<i>Use</i> /find <i>to connect.</i>"
DAILY_NEXT_LIMIT_REACHED_TEXT = (
    "⏳ <b>You've used all {limit} of your daily credits.</b>\n"
    "<i>Credits are spent on /next skips and (for free-tier users) photo sends.</i>\n"
    "<i>Your count resets at midnight UTC, or</i> /subscribe <i>for more credits + unlimited photos.</i>"
)

# ---------------------------------------------------------------------------
# commands/subscribe.py
# ---------------------------------------------------------------------------
SUBSCRIBE_INTRO_TEXT = (
    "⭐ <b>Chat Zone Subscription</b>\n\n"
    "{status}\n\n"
    "<b>Perks on any active plan:</b>\n"
    "• Higher daily credit limit (more skips)\n"
    "• Send unlimited photos — free-tier photo sends cost 1 daily credit each\n"
    "• Unlock /private (Privacy Mode) for photos/videos/voice notes\n"
    "• Get a peek at your partner's details when matched\n\n"
    "<b>Pick a plan:</b>"
)
SUBSCRIBE_INVOICE_TITLE = "Chat Zone — {label} Plan"
SUBSCRIBE_INVOICE_DESCRIPTION = (
    "{label} subscription: daily credit limit of {limit}, unlimited photos, "
    "Privacy Mode access, partner details on match, and {points} bonus points."
)
SUBSCRIBE_PAYMENT_SUCCESS_TEXT = (
    "✅ <b>{label} plan activated!</b>\n"
    "<i>Active until:</i> <code>{expires}</code>\n"
    "<i>+{points} points added to your account 🎉</i>\n"
    "<i>Daily credit limit is now</i> <b>{limit}</b> — <i>and your photos are unlimited & free.</i>"
)

# ---------------------------------------------------------------------------
# commands/admin_commands.py - /giveaway
# ---------------------------------------------------------------------------
GIVEAWAY_USAGE_TEXT = (
    "<i>Usage:</i> <code>/giveaway &lt;user_id&gt; &lt;tier&gt;</code>\n"
    "<i>Tier is one of:</i> <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"
)
GIVEAWAY_UNKNOWN_TIER_TEXT = "<i>Unknown tier. Use one of:</i> <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"

# ---------------------------------------------------------------------------
# media_privacy.py / relay.py
# ---------------------------------------------------------------------------
PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT = (
    "🔒 <b>Privacy Mode is a subscriber perk.</b>\n"
    "<i>Your media was sent as a normal message instead. Use</i> /subscribe <i>to unlock Privacy Mode.</i>"
)
PHOTO_DAILY_LIMIT_REACHED_TEXT = (
    "📷 <b>You've used all {limit} of your daily credits, so this photo wasn't sent.</b>\n"
    "<i>Your count resets at midnight UTC, or</i> /subscribe <i>for unlimited photos.</i>"
)

# ---------------------------------------------------------------------------
# commands/games.py
# ---------------------------------------------------------------------------
NEED_PARTNER_FOR_GAME_TEXT = "<i>You need a partner first. Use</i> /find <i>to get matched up!</i>"
PICK_GAME_TEXT = "🎮 <b>Pick a game to challenge your partner to:</b>"
SENDING_GAME_REQUEST_TEXT = "⏳ <i>Sending your game request...</i>"

# ---------------------------------------------------------------------------
# commands/help.py
# ---------------------------------------------------------------------------
HELP_TEXT = (
    "🤖 <b>Chat Zone - Anonymous Chat Bot</b>\n\n"
    "<i>Connect with strangers and chat anonymously right here on Telegram.</i>\n\n"
    "\t\tThis bot relays text, stickers, photos, videos, GIFs, voice and video notes between you and your partner. "
    "To send a photo, video, voice note or video note in <b>Privacy Mode</b>, where it disappears from the "
    "chat as soon as your partner opens it, once, and can't be forwarded or saved. To use this feature "
    "caption the media file with /private, or send /private on its own first and then send the media right after.\n\n"
    "<b>Commands:</b>\n"
    "/start - <i>Show the welcome message</i>\n"
    "/find - <i>Find a new partner (matched by shared interests when possible)</i>\n"
    "/next - <i>Skip the current chat and find someone new</i>\n"
    "/stop - <i>Stop the current chat</i>\n"
    "/profile - <i>Show your profile, edit your info & interests</i>\n"
    "/games - <i>Play a mini-game with your partner</i>\n"
    "/coinsteal - <i>Quick-start a game of Coin Steal</i>\n"
    "/private - <i>Arm Privacy Mode, then send your media right after</i>\n"
    "/help - <i>Show this message</i>\n\n"
    "<b>Staying safe:</b>\n"
    "\t\tEvery chat ends with the option to rate or report your partner. Reports are reviewed and repeated "
    "bad behaviour gets punished automatically. If you ever get restricted and think it's a mistake, "
    "just reach out to a bot admin to get it sorted."
)

# ---------------------------------------------------------------------------
# commands/admin_commands.py
# ---------------------------------------------------------------------------
GIVE_BROADCAST_MESSAGE_TEXT = "<i>Give me a message to broadcast!</i>"
GIVE_VALID_CONNECT_USER_ID_TEXT = "<i>Give me a valid user id to connect.</i>"
TARGET_NOT_IN_DB_TEXT = "<i>The target user isn't in our database.</i>"
ALREADY_CONNECTED_TO_TARGET_TEXT = "<i>You are already connected to the target.</i>"

ADMIN_HELP_TEXT = (
    "<b>Admin commands:</b>\n"
    "<code>/ban &lt;user_id&gt; &lt;severity 0-10&gt; [reason]</code>\n"
    "<code>/unban &lt;user_id&gt;</code>\n"
    "<code>/checkuser &lt;user_id&gt;</code>\n"
    "<code>/connect &lt;user_id&gt;</code>\n"
    "<code>/broadcast &lt;message&gt;</code>"
)

BAN_USAGE_TEXT = "<i>Usage:</i> <code>/ban &lt;user_id&gt; &lt;severity 0-10&gt; [reason]</code>"
SEVERITY_RANGE_TEXT = "<i>Severity has to be between 0 and 10.</i>"
CANT_RESTRICT_SELF_TEXT = "<i>You can't restrict yourself.</i>"
ADMINS_CANT_BE_RESTRICTED_TEXT = "<i>Admins can't be restricted.</i>"
SEVERITY_ZERO_NOOP_TEXT = "<i>Severity 0 doesn't restrict anyone, nothing changed.</i>"
UNBAN_USAGE_TEXT = "<i>Usage:</i> <code>/unban &lt;user_id&gt;</code>"
GIVE_VALID_USER_ID_TEXT = "<i>Give me a valid user id.</i>"
RESTRICTION_LIFTED_TEXT = "✅ <i>Your restriction has been lifted by an admin.</i>"
CHECKUSER_USAGE_TEXT = "<i>Usage:</i> <code>/checkuser &lt;user_id&gt;</code>"
NO_RECORD_OF_USER_TEXT = "<i>No record of this user.</i>"
NOT_RESTRICTED_TEXT = "✅ Not restricted"
NO_REPORTS_TEXT = "  <i>None</i>"

# ---------------------------------------------------------------------------
# commands/stop.py
# ---------------------------------------------------------------------------
CHAT_ENDED_TEXT = "👋 <b>Chat ended.</b>"
REMOVED_FROM_QUEUE_TEXT = "❗ <b>You've been removed from the waiting queue.</b>\n<i>Use</i> /find <i>to search for a partner.</i>"
NOT_IN_CHAT_TEXT = "❗ <b>You're not in a chat.</b>"

# ---------------------------------------------------------------------------
# handlers/rating.py
# ---------------------------------------------------------------------------
RATE_PROMPT_TEXT = "💡 <i>If your chat partner misbehaved or broke the rules, report them below.</i>\n<i>You can also rate them, which affects their profile rating.</i>"
REPORT_REASON_PROMPT_TEXT = "🚩 <b>What happened?</b> <i>Pick the closest reason:</i>"
REPORT_LOGGED_TEXT = "✅ <b>Thanks, we've logged that report.</b>\n<i>Your feedback helps keep this bot safe.</i>"
FEEDBACK_THANKS_TEXT = "<b>Thank you for your feedback.</b>\n<i>It helps keep everyone here safe.</i>"

# ---------------------------------------------------------------------------
# handlers/preferences.py
# ---------------------------------------------------------------------------
PREFERENCES_INTRO_FIRST_TIME_TEXT = (
    "🏷️ <b>Pick what you're into — this helps us match you with people who share your vibe.</b>\n"
    "Tap to toggle, hit Done when you're happy with the list. Totally optional."
)
PREFERENCES_INTRO_UPDATE_TEXT = "🏷️ <b>Update your interests:</b>"
DONE_BUTTON_LABEL = "✅ Done"
DONE_SKIP_BUTTON_LABEL = "✅ Done / Skip"
NONE_PICKED_YET_TEXT = "None picked yet"

# ---------------------------------------------------------------------------
# handlers/setup.py
# ---------------------------------------------------------------------------
WELCOME_NEW_USER_TEXT = "👋 <i>Welcome to</i> <b>Chat Zone - Anonymous Chat Bot!</b>"
SETUP_PROFILE_GENDER_PROMPT_TEXT = "<b>Let's set up your profile.</b>\n<i>What's your gender?</i>"
SELECT_GENDER_TEXT = "<b>Please select your gender:</b>"
ENTER_AGE_TEXT = "📅 <b>Please enter your age:</b>"
INVALID_AGE_TEXT = "❌ <b>Please enter a valid age.</b>"
PREFERENCES_BUTTONS_NUDGE_TEXT = "🏷️ <i>Use the buttons above to pick your interests, then hit Done.</i>"

# ---------------------------------------------------------------------------
# handlers/edit.py
# ---------------------------------------------------------------------------
SELECT_NEW_GENDER_TEXT = "<b>Select your new gender:</b>"
ENTER_NEW_AGE_TEXT = "📅 <b>Please enter your new age:</b>"

# ---------------------------------------------------------------------------
# handlers/country.py
# ---------------------------------------------------------------------------
SELECT_COUNTRY_TEXT = "🌍 <b>Select your country:</b>"

# ---------------------------------------------------------------------------
# relay.py
# ---------------------------------------------------------------------------
FAILED_TO_SEND_MESSAGE_TEXT = "❌ <b>Failed to send message.</b>"
NOT_IN_CHAT_USE_FIND_INLINE_TEXT = "❗ <b>You're not in a chat.</b> Use /find to connect."

# ---------------------------------------------------------------------------
# media_privacy.py
# ---------------------------------------------------------------------------
SENT_PRIVACY_MODE_TEXT = "🔒 <i>Sent in Privacy Mode. It'll be gone once they've seen it.</i>"
PRIVACY_MODE_PLACEHOLDER_TEXT = "🔒 <b>Privacy Mode media</b>\n<iIt disappears after you open it.</i>"
PRIVACY_MEDIA_NO_LONGER_AVAILABLE_ALERT = "This media is no longer available."
PRIVACY_MEDIA_NO_LONGER_AVAILABLE_TEXT = "🔒 <i>This Privacy Mode media is no longer available.</i>"
NOT_FOR_YOU_ALERT = "This isn't for you."
ALREADY_VIEWED_ALERT = "Already viewed. It's gone."
ALREADY_VIEWED_TEXT = "🔒 <i>This has already been viewed and is no longer available.</i>"
YOUR_MEDIA_VIEWED_TEXT = "👀 <i>Your Privacy Mode media has been viewed.</i>"
PRIVACY_MEDIA_EXPIRED_EDIT_TEXT = "🔒 This Privacy Mode media expired unopened."
PRIVACY_MEDIA_EXPIRED_DM_TEXT = "⌛ <i>Your Privacy Mode media went unopened and has expired.</i>"

# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
BOT_RUNNING_STATUS_TEXT = "✅ Anonymous Chat Bot is running!"

# ---------------------------------------------------------------------------
# games/game_requests.py
# ---------------------------------------------------------------------------
NO_PARTNER_FOR_GAME_TEXT = "<i>No partner found. Go get one with</i> /find <i>first 💀.</i>"
CANT_PLAY_WITH_YOURSELF_TEXT = "<i>Are you really trying to play with yourself 💀.</i>"
ALREADY_IN_GAME_TEXT = "<i>You're already in a game. Finish that first.</i>"
PARTNER_ALREADY_IN_GAME_TEXT = "<i>Your partner is already in a game. Let them finish first.</i>"
CANT_SPAM_GAME_REQUESTS_TEXT = "<i>You can't just spam requests and expect your partner to accept it 💀.</i>"
WAITING_FOR_PARTNER_ACCEPT_TEXT = "⏳ <b>Waiting for your partner to accept...</b>"
GAME_REQUEST_EXPIRED_TEXT = "<i>This request expired or doesn't exist.</i>"
YOU_DECLINED_REQUEST_TEXT = "<i>You declined the request.</i>"
PARTNER_DECLINED_REQUEST_TEXT = "<i>Your partner has declined the request.</i>"

# ---------------------------------------------------------------------------
# Shared across multiple mini-games (games/coin_steal.py, rps.py, tictactoe.py,
# guess_it.py, would_you_rather.py)
# ---------------------------------------------------------------------------
PARTNER_LEFT_GAME_TEXT = "<i>Your partner left the game. Game ended...</i>"
GAME_ENDED_INACTIVITY_TEXT = "<i>Game ended due to inactivity.</i>"
WON_MATCH_TEXT = "🏆 <b>You won the match!</b> +8 points."
LOST_MATCH_TEXT = "😔 <b>You lost the match.</b> Rematch sometime?"

# ---------------------------------------------------------------------------
# commands/cancel.py
# ---------------------------------------------------------------------------
GAME_CANCELLED_TEXT = "🛑 <b>Game cancelled.</b> \nYour chat is still open, use /games to start another."
GAME_REQUEST_CANCELLED_TEXT = "🛑 <b>Game request cancelled.</b>"
PARTNER_CANCELLED_REQUEST_TEXT = "<i>Your partner cancelled the game request.</i>"
NOTHING_TO_CANCEL_TEXT = "<i>You don't have an active game or pending game request to cancel.</i>"

# ---------------------------------------------------------------------------
# games/coin_steal.py
# ---------------------------------------------------------------------------
ALREADY_CHOSE_TEXT = "<i>You already chose. Chill 😭</i>"
CHOICE_LOCKED_IN_TEXT = "<i>Your choice has been locked in 🔒.</i>"
OPPONENT_MOVED_TEXT = "<i>Your opponent made their move... Do you trust them? 👀</i>"
MUTUAL_SAVE_NO_STREAK_TEXT = "<i>You guys really trusted each other! 👀\nGood job saving your coins for now 😏</i>"
BOTH_STOLE_TEXT = "<i>Both chose greed over the other and stole. Now no one wins 😏.</i>"
GOT_STOLEN_FROM_TEXT = "<i>You shouldn't have done that to them 💀. They tried to save their coin and you just stole it...</i>"
TRUSTED_WRONG_ONE_TEXT = "<i>You sure trusted the wrong one this time 💀. You just got stolen...</i>"
COIN_STEAL_END_INTRO_TEXT = "<i>The game has come to an end. Well played both of you.</i>\n\n"
WON_BY_DECEIVING_TEXT = "<i>You really won by deceiving them 💔.</i>"
LOST_TRUST_LESSON_TEXT = "<i>Maybe that's why they tell us not to trust anyone on the internet 🥀.</i>"
COIN_STEAL_DRAW_TEXT = "<i>You guys managed to make it a draw 👏. Well played for sure!</i>"
COIN_STEAL_TIMEOUT_TEXT = "<i>Game ended due to inactivity.\nRestart if you guys wanna play again.</i>"

# ---------------------------------------------------------------------------
# games/rps.py
# ---------------------------------------------------------------------------
OPPONENT_ALREADY_PICKED_TEXT = "<i>Your opponent already picked.</i> Your move..."

# ---------------------------------------------------------------------------
# games/tictactoe.py
# ---------------------------------------------------------------------------
DRAW_NOTE_TEXT = "\n\n🤝 <b>It's a draw!</b> Well played both of you."
GAME_OVER_NOTE_TEXT = "\n\n🏆 <b>Game over!</b>"
