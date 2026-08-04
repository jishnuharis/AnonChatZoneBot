# ---------------------------------------------------------------------------
# commands/start.py
# ---------------------------------------------------------------------------
WELCOME_BACK_TEXT = "👋 <i>Welcome back to</i> <b>Chat Zone - Anonymous Chat Bot!</b>\nUse /find to look for a partner."

# ---------------------------------------------------------------------------
# commands/find.py
# ---------------------------------------------------------------------------
ALREADY_IN_CHAT_TEXT = "⚠️ <b>You're already in a chat.</b>\nUse /stop or /next first."
LOOKING_FOR_PARTNER_TEXT = "🔍 <b>Looking for a partner...</b>\nMatching you with someone who shares your interests if possible."

# ---------------------------------------------------------------------------
# commands/next.py
# ---------------------------------------------------------------------------
PARTNER_LEFT_CHAT_TEXT = "⛔ <b>Your partner left the chat.</b>"
PARTNER_SKIPPED_TEXT = "🔁 <b>Partner skipped...</b>\nYou're added to the waiting queue, finding a new one..."
NOT_IN_CHAT_USE_FIND_TEXT = "❗ <b>You're not in a chat.</b>\nUse /find to connect."
DAILY_NEXT_LIMIT_REACHED_TEXT = (
    "⏳ <b>You've used all {limit} of your daily credits.</b>\n"
    "Credits are spent on /next skips and (for free-tier users) media files sends.\n\n"
    "Your count resets at midnight UTC, or /subscribe for more credits + unlimited media files."
)

# ---------------------------------------------------------------------------
# commands/subscribe.py
# ---------------------------------------------------------------------------
SUBSCRIBE_INTRO_TEXT = (
    "⭐ <b>Chat Zone Subscription</b>\n\n"
    "{status}\n\n"
    "<b>Perks on any active plan:</b>\n"
    "• Higher daily credit limit (more skips)\n"
    "• Send unlimited photos, videos, voice & video notes — free-tier media sends cost 1 daily credit each\n"
    "• Unlock /private (Privacy Mode) for photos/videos/voice notes\n"
    "• Get a peek at your partner's details when matched\n\n"
    "<b>Pick a plan:</b>"
)
SUBSCRIBE_INVOICE_TITLE = "Chat Zone — {label} Plan"
SUBSCRIBE_INVOICE_DESCRIPTION = (
    "{label} subscription: daily credit limit of {limit}, unlimited media sends, "
    "Privacy Mode access, partner details on match, and {points} bonus points."
)
SUBSCRIBE_PAYMENT_SUCCESS_TEXT = (
    "✅ <b>{label} plan activated!</b>\n"
    "<i>Active until:</i> <code>{expires}</code>\n"
    "<b>+{points}</b> points added to your account 🎉\n"
    "Daily credit limit is now <b>{limit}</b> — and your media sends are unlimited & free."
)

# ---------------------------------------------------------------------------
# commands/admin_commands.py - /giveaway
# ---------------------------------------------------------------------------
GIVEAWAY_USAGE_TEXT = (
    "<i>Usage:</i> <code>/giveaway &lt;user_id&gt; &lt;tier&gt;</code>\n"
    "<i>Tier is one of:</i> <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"
)
GIVEAWAY_UNKNOWN_TIER_TEXT = "<i>Unknown tier.</i> Use one of: <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"

# ---------------------------------------------------------------------------
# media_privacy.py / relay.py
# ---------------------------------------------------------------------------
PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT = (
    "🔒 <b>Privacy Mode is a subscriber perk.</b>\n"
    "Your media will be sent as a normal message instead. Use /subscribe to unlock Privacy Mode."
)
MEDIA_DAILY_LIMIT_REACHED_TEXT = (
    "📷 <b>You've used all {limit} of your daily credits, so this {kind} wasn't sent.</b>\n"
    "Your count resets at midnight UTC, or /subscribe for unlimited media sends."
)

# ---------------------------------------------------------------------------
# commands/games.py
# ---------------------------------------------------------------------------
NEED_PARTNER_FOR_GAME_TEXT = "<b>You need a partner first.</b>\n Use /find to get matched up!"
PICK_GAME_TEXT = "🎮 <b>Pick a game to challenge your partner to:</b>"
SENDING_GAME_REQUEST_TEXT = "⏳ <b>Sending your game request...</b>"

# ---------------------------------------------------------------------------
# commands/help.py
# ---------------------------------------------------------------------------
HELP_TEXT = (
    "🤖 <b>Chat Zone - Anonymous Chat Bot</b>\n\n"
    "<i>Connect with strangers and chat anonymously right here on Telegram.</i>\n\n"
    "\t\tThis bot relays text, stickers, photos, videos, GIFs, voice and video notes between you and your partner. "
    "Want to break the ice? Challenge your partner to a mini-game with /games - Tic Tac Toe, Rock Paper Scissors, "
    "Guess It, Would You Rather, or Coin Steal.\n\n"
    "<b>Commands:</b>\n"
    "/start - <i>Show the welcome message</i>\n"
    "/find - <i>Find a new partner (matched by shared interests when possible)</i>\n"
    "/next - <i>Skip the current chat and find someone new</i>\n"
    "/stop - <i>Stop the current chat</i>\n"
    "/profile - <i>Show your profile, edit your info & interests</i>\n"
    "/games - <i>Play a mini-game with your partner</i>\n"
    "/private - <i>Send a photo, video, voice or video note in Privacy Mode, where it disappears once your "
    "partner opens it and can't be forwarded or saved, caption your media with /private, or send /private "
    "on its own first and then the media right after</i>\n"
    "/subscribe - <i>View plans for higher daily credits, unlimited media sends & Privacy Mode access</i>\n"
    "/help - <i>Show this message</i>\n\n"
    "<b>Daily credits:</b>\n"
    "\t\tFree accounts share a daily credit pool between /next skips and photo/video/voice/video note sends, resetting at midnight UTC. "
    "Subscribers get a bigger pool, unlimited free media sends, and unlock Privacy Mode — see /subscribe for plans.\n\n"
    "<b>Referral bonus:</b>\n"
    "\t\tGrab your personal invite link anytime from the 🔗 button on /profile. When a referral promo is running, "
    "getting enough friends to join through it and finish setting up their profile earns you a free subscription — "
    "you might also see this pop up while using the bot.\n\n"
    "<b>Staying safe:</b>\n"
    "\t\tEvery chat ends with the option to rate or report your partner. Reports are reviewed and repeated "
    "bad behaviour gets punished automatically. If you ever get restricted and think it's a mistake, "
    "just reach out to a bot admin to get it sorted."
)

# ---------------------------------------------------------------------------
# commands/admin_commands.py
# ---------------------------------------------------------------------------
GIVE_BROADCAST_MESSAGE_TEXT = "<b>Give me a message to broadcast!</b>"
GIVE_VALID_CONNECT_USER_ID_TEXT = "<b>Give me a valid user id to connect.</b>"
TARGET_NOT_IN_DB_TEXT = "<b>The target user isn't in our database.</b>"
ALREADY_CONNECTED_TO_TARGET_TEXT = "<b>You are already connected to the target.</b>"

ADMIN_HELP_TEXT = (
    "<b>Admin commands:</b>\n"
    "\t\t<i>/ban</i> - <code>/ban &lt;user_id&gt; &lt;severity 0-10&gt; [reason]</code>\n"
    "\t\t<i>/unban</i> - <code>/unban &lt;user_id&gt;</code>\n"
    "\t\t<i>/checkuser</i> - <code>/checkuser &lt;user_id&gt;</code>\n"
    "\t\t<i>/connect</i> - <code>/connect &lt;user_id&gt;</code>\n"
    "\t\t<i>/broadcast</i> - <code>/broadcast &lt;message&gt;</code>\n"
    "\t\t<i>/giveaway</i> - <code>/giveaway &lt;user_id&gt; &lt;tier&gt;</code>\n"
    "\t\t<i>/referral</i> - <code>/referral &lt;required_referrals&gt; &lt;promo_duration_days&gt;</code>"
)

BAN_USAGE_TEXT = "<i>Usage:</i> <code>/ban &lt;user_id&gt; &lt;severity 0-10&gt; [reason]</code>"
SEVERITY_RANGE_TEXT = "<b>Severity has to be between 0 and 10.</b>"
CANT_RESTRICT_SELF_TEXT = "<b>You can't restrict yourself.</b>"
ADMINS_CANT_BE_RESTRICTED_TEXT = "<b>Admins can't be restricted.</b>"
SEVERITY_ZERO_NOOP_TEXT = "<b>Severity 0 doesn't restrict anyone, nothing changed.</b>"
UNBAN_USAGE_TEXT = "<i>Usage:</i> <code>/unban &lt;user_id&gt;</code>"
GIVE_VALID_USER_ID_TEXT = "<b>Give me a valid user id.</b>"
RESTRICTION_LIFTED_TEXT = "✅ <b>Your restriction has been lifted by an admin.</b>"
CHECKUSER_USAGE_TEXT = "<i>Usage:</i> <code>/checkuser &lt;user_id&gt;</code>"
NO_RECORD_OF_USER_TEXT = "<b>No record of this user.</b>"
NOT_RESTRICTED_TEXT = "✅ Not restricted"
NO_REPORTS_TEXT = "\t\tNone"

REFERRAL_USAGE_TEXT = (
    "<i>Usage:</i> <code>/referral &lt;required_referrals&gt; &lt;promo_duration_days&gt;</code>\n"
    "<i>e.g.</i> <code>/referral 5 7</code> - refer 5 friends who finish setup, get a free weekly "
    "subscription, repeatable - promo stays live for 7 days.\n\n"
    "<i>To turn it off:</i>\n\t<code>/referral &lt;required_referrals&gt; 0</code>,"
    "\n\t<code>/referral -1 &lt;promo_duration_days&gt;</code>, or both."
)
REFERRAL_DISABLED_TEXT = "🛑 <b>Referral scheme turned off.</b>"

# ---------------------------------------------------------------------------
# commands/stop.py
# ---------------------------------------------------------------------------
CHAT_ENDED_TEXT = "👋 <b>Chat ended.</b>"
REMOVED_FROM_QUEUE_TEXT = "❗ <b>You've been removed from the waiting queue.</b>\nUse /find to search for a partner."
NOT_IN_CHAT_TEXT = "❗ <b>You're not in a chat.</b>"

# ---------------------------------------------------------------------------
# handlers/rating.py
# ---------------------------------------------------------------------------
RATE_PROMPT_TEXT = "💡 <b>If your chat partner misbehaved or broke the rules, report them below.</b>\nYou can also rate them, which affects their profile rating."
REPORT_REASON_PROMPT_TEXT = "🚩 <b>What happened?</b> Pick the closest reason:"
REPORT_LOGGED_TEXT = "✅ <b>Thanks, we've logged that report.</b>\nYour feedback helps keep this bot safe."
FEEDBACK_THANKS_TEXT = "<b>Thank you for your feedback.</b>\nIt helps keep everyone here safe."

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
SETUP_PROFILE_GENDER_PROMPT_TEXT = "<b>Let's set up your profile.</b>\nWhat's your gender?"
SELECT_GENDER_TEXT = "<b>Please select your gender:</b>"
ENTER_AGE_TEXT = "📅 <b>Please enter your age:</b>"
INVALID_AGE_TEXT = "❌ <b>Please enter a valid age.</b>"
PREFERENCES_BUTTONS_NUDGE_TEXT = "🏷️<b>Let us know your preferences</b>\nUse the buttons above to pick your interests, then hit <b>Done</b>."

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
NOT_IN_CHAT_USE_FIND_INLINE_TEXT = "❗ <b>You're not in a chat.</b>\nUse /find to connect."

# ---------------------------------------------------------------------------
# media_privacy.py
# ---------------------------------------------------------------------------
SENT_PRIVACY_MODE_TEXT = "🔒 <i>Sent in <b>Privacy Mode</b>.</i>\nIt'll be gone once they've seen it."
PRIVACY_MODE_PLACEHOLDER_TEXT = "🔒 <b>Privacy Mode media</b>\nIt disappears after you open it."
PRIVACY_MEDIA_NO_LONGER_AVAILABLE_ALERT = "This media is no longer available."
PRIVACY_MEDIA_NO_LONGER_AVAILABLE_TEXT = "🔒 <b>This Privacy Mode media is no longer available.</b>"
NOT_FOR_YOU_ALERT = "This isn't for you."
ALREADY_VIEWED_ALERT = "Already viewed. It's gone."
ALREADY_VIEWED_TEXT = "🔒 <b>This has already been viewed and is no longer available.</b>"
YOUR_MEDIA_VIEWED_TEXT = "👀 <b>Your Privacy Mode media has been viewed.</b>"
PRIVACY_MEDIA_EXPIRED_EDIT_TEXT = "🔒 <b>This Privacy Mode media expired unopened.</b>"
PRIVACY_MEDIA_EXPIRED_DM_TEXT = "⌛ <b>Your Privacy Mode media went unopened and has expired.</b>"

# ---------------------------------------------------------------------------
# app.py
# ---------------------------------------------------------------------------
BOT_RUNNING_STATUS_TEXT = "✅ Anonymous Chat Bot is running!"

# ---------------------------------------------------------------------------
# games/game_requests.py
# ---------------------------------------------------------------------------
NO_PARTNER_FOR_GAME_TEXT = "<b>No partner found.</b> Go get one with /find first 💀."
CANT_PLAY_WITH_YOURSELF_TEXT = "<b>Are you really trying to play with yourself 💀.</b>"
ALREADY_IN_GAME_TEXT = "<b>You're already in a game.</b>\nFinish that first or use /cancel to cancel the currently running game."
PARTNER_ALREADY_IN_GAME_TEXT = "<b>Your partner is already in a game.</b>\nLet them finish first."
CANT_SPAM_GAME_REQUESTS_TEXT = "<b>You can't just spam requests and expect your partner to accept it 💀.</b>"
WAITING_FOR_PARTNER_ACCEPT_TEXT = "⏳ <b>Waiting for your partner to accept...</b>"
GAME_REQUEST_EXPIRED_TEXT = "<b>This request expired or doesn't exist.</b>"
YOU_DECLINED_REQUEST_TEXT = "<b>You declined the request.</b>"
PARTNER_DECLINED_REQUEST_TEXT = "<b>Your partner has declined the request.</b>"

# ---------------------------------------------------------------------------
# Shared across multiple mini-games (games/coin_steal.py, rps.py, tictactoe.py,
# guess_it.py, would_you_rather.py)
# ---------------------------------------------------------------------------
PARTNER_LEFT_GAME_TEXT = "<b>Your partner left the game.</b>\nGame ended..."
GAME_ENDED_INACTIVITY_TEXT = "<b>Game ended due to inactivity.</b>"
WON_MATCH_TEXT = "🏆 <b>You won the match!</b> +8 points."
LOST_MATCH_TEXT = "😔 <b>You lost the match.</b> Rematch sometime?"

# ---------------------------------------------------------------------------
# commands/cancel.py
# ---------------------------------------------------------------------------
GAME_CANCELLED_TEXT = "🛑 <b>Game cancelled.</b> \nYour chat is still open, use /games to start another."
GAME_REQUEST_CANCELLED_TEXT = "🛑 <b>Game request cancelled.</b>"
PARTNER_CANCELLED_REQUEST_TEXT = "<b>Your partner cancelled the game request.</b>"
NOTHING_TO_CANCEL_TEXT = "<b>You don't have an active game or pending game request to cancel.</b>"

# ---------------------------------------------------------------------------
# games/coin_steal.py
# ---------------------------------------------------------------------------
ALREADY_CHOSE_TEXT = "<b>You already chose.</b> Chill 😭"
CHOICE_LOCKED_IN_TEXT = "<b>Your choice has been locked in 🔒.</b>"
OPPONENT_MOVED_TEXT = "<b>Your opponent made their move...<\b> Do you trust them? 👀"
MUTUAL_SAVE_NO_STREAK_TEXT = "<b>You guys really trusted each other!</b> 👀\nGood job saving your coins for now 😏"
BOTH_STOLE_TEXT = "<b>Both chose greed over the other and stole.</b>\nNow no one wins 😏."
GOT_STOLEN_FROM_TEXT = "<b>You shouldn't have done that to them 💀.</b>\nThey tried to save their coin and you just stole it..."
TRUSTED_WRONG_ONE_TEXT = "<b>You sure trusted the wrong one this time 💀.</b>\nYou just got stolen..."
COIN_STEAL_END_INTRO_TEXT = "<b>The game has come to an end.</b>\nWell played both of you.\n\n"
WON_BY_DECEIVING_TEXT = "<b>You really won by deceiving them 💔.</b>"
LOST_TRUST_LESSON_TEXT = "<b>Maybe that's why they tell us not to trust anyone on the internet 🥀.</b>"
COIN_STEAL_DRAW_TEXT = "<b>You guys managed to make it a draw 👏.</b>\nWell played for sure!"
COIN_STEAL_TIMEOUT_TEXT = "<b>Game ended due to inactivity.</b>\nRestart if you guys wanna play again."

# ---------------------------------------------------------------------------
# games/rps.py
# ---------------------------------------------------------------------------
OPPONENT_ALREADY_PICKED_TEXT = "<b>Your opponent already picked.</b>\nYour move..."

# ---------------------------------------------------------------------------
# games/tictactoe.py
# ---------------------------------------------------------------------------
DRAW_NOTE_TEXT = "\n\n🤝 <b>It's a draw!</b>\nWell played both of you."
GAME_OVER_NOTE_TEXT = "\n\n🏆 <b>Game over!</b>"
