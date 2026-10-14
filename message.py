# ---------------------------------------------------------------------------
# commands/start.py
# ---------------------------------------------------------------------------
WELCOME_BACK_TEXT = "👋 <i>Welcome back to</i> <b>Chat Zone - Anonymous Chat Bot!</b>\n\nUse /find to look for a partner."

# ---------------------------------------------------------------------------
# commands/find.py
# ---------------------------------------------------------------------------
ALREADY_IN_CHAT_TEXT = "⚠️ <b>You're already in a chat.</b>\n\nUse /stop or /next first."
LOOKING_FOR_PARTNER_TEXT = "🔍 <b>Looking for a partner...</b>\n\nMatching you with someone who shares your interests if possible."

# ---------------------------------------------------------------------------
# commands/next.py
# ---------------------------------------------------------------------------
PARTNER_LEFT_CHAT_TEXT = "⛔ <b>Your partner left the chat.</b>"
PARTNER_SKIPPED_TEXT = "🔁 <b>Partner skipped...</b>\n\nYou're added to the waiting queue, finding a new one..."
NOT_IN_CHAT_USE_FIND_TEXT = "❗ <b>You're not in a chat.</b>\n\nUse /find to connect."
DAILY_NEXT_LIMIT_REACHED_TEXT = (
    "⏳ <b>You've reached your daily chat limit ({limit} credits used).</b>\n\n"
    "Daily credits limit how many users you can chat with each day (used by /find and /next) as well as media sends for free accounts.\n\n"
    "Your daily limit resets at midnight UTC, or /subscribe to chat with more partners + unlock unlimited media sends!"
)

# ---------------------------------------------------------------------------
# commands/subscribe.py
# ---------------------------------------------------------------------------
SUBSCRIBE_INTRO_TEXT = (
    "👑 <b>Chat Zone Subscription — VIP Membership</b> 👑\n\n"
    "{status}\n\n"
    "<blockquote>⚡ <b>VIP Plans Unlock:</b>\n"
    "🎯 <b>Target Filters:</b> Match only with who you want (Guys/Girls/Country).\n"
    "🗑️ <b>Two-Way Wipe:</b> Reply /prune to erase any message on both sides.\n"
    "👀 <b>Gender Peek:</b> Know who you're talking to before you say hi.\n"
    "🚀 <b>Priority Queue:</b> Cut the line. Zero waiting for matches.\n"
    "📞 <b>Private Calls:</b> Talk live 1-on-1 with unlimited voice call time.\n"
    "💣 <b>Ghost Media:</b> Send self-destructing view-once photos (45s).</blockquote>\n\n"
    "📦 <b>Choose Your VIP Tier:</b>\n\n"
    "⚡ <b>1 Day Pass — <code>25 ⭐</code></b> <i>(Direct: ₹20 / $0.24)</i>\n"
    "└ <i>Full VIP Powers • 48 Chats/Day • 32 Friends • +50 Pts</i>\n\n"
    "✨ <b>1 Week Pass — <code>125 ⭐</code></b> <i>(Direct: ₹100 / $1.20)</i>\n"
    "└ <i>Full VIP Powers • 64 Chats/Day • 48 Friends • +200 Pts</i>\n\n"
    "🌙 <b>1 Month VIP — <code>450 ⭐</code></b> <i>(Direct: ₹300 / $3.60)</i> 🔥\n"
    "└ <i>Full VIP Powers • 80 Chats/Day • 64 Friends • +800 Pts (Save ~50%)</i>\n\n"
    "👑 <b>1 Year Legend — <code>4,500 ⭐</code></b> <i>(Direct: ₹2,400 / $28.80)</i> 🎁\n"
    "└ <i>Full VIP Powers • 96 Chats/Day • Crown Badge 👑 • 80 Friends • +3,500 Pts (Save ~70%)</i>\n\n"
    "👉 <a href=\"{admin_url}\">Tap here to buy directly from Admin (UPI/Crypto/Card)</a>\n\n"
    "⭐ <i>Or activate instantly with Telegram Stars below:</i>"
)

SUBSCRIBE_COMPARE_TEXT = (
    "📋 <b>VIP PERKS COMPARISON MATRIX</b>\n\n"
    "<blockquote><b>✨ Universal VIP Features (Included in ALL Plans):</b>\n"
    "• 🎯 Gender & Country Match Filters\n"
    "• 🗑️ Two-Way Wipe: Reply /prune to delete on both screens\n"
    "• 👀 Partner Gender Peek on match\n"
    "• 📞 Unlimited 1-on-1 Voice Calls\n"
    "• 💣 Ghost Media (/private) Self-Destructing Photos\n"
    "• 🚀 Priority Matchmaking Queue\n"
    "• ⚡ Instant Media (No warmup lock) & HIGHER DAILY CHATS</blockquote>\n\n"
    "<blockquote><b>⚡ Daily (25 ⭐ / ₹20)</b>\n"
    "• 48 Daily Chats (vs 32 Free)\n"
    "• 24 Hours VIP Access\n"
    "• 32 Friends Slots • +50 Points Bonus\n"
    "• Badge: ⚡ Daily VIP</blockquote>\n\n"
    "<blockquote><b>✨ Weekly (125 ⭐ / ₹100)</b>\n"
    "• 64 Daily Chats\n"
    "• 7 Days VIP Access\n"
    "• 48 Friends Slots • +200 Points Bonus\n"
    "• Badge: ✨ Weekly VIP</blockquote>\n\n"
    "<blockquote><b>🌙 Monthly (450 ⭐ / ₹300) 🔥</b>\n"
    "• 80 Daily Chats\n"
    "• 30 Days VIP Access (Save ~50%)\n"
    "• 64 Friends Slots • +800 Points Bonus\n"
    "• Badge: 🌙 Monthly VIP</blockquote>\n\n"
    "<blockquote><b>👑 Yearly Legend (4,500 ⭐ / ₹2,400) 🎁</b>\n"
    "• 96 Daily Chats (Maximum allowed)\n"
    "• 365 Days VIP Access (Save ~70%)\n"
    "• 80 Friends Slots • +3,500 Points Bonus\n"
    "• Badge: 👑 Crown VIP (Profile & Leaderboard)</blockquote>\n\n"
    "👉 <a href=\"{admin_url}\">Contact Admin for Direct UPI/Card/Crypto Activation</a>"
)

SUBSCRIBE_INVOICE_TITLE = "Chat Zone — {label} Plan"
SUBSCRIBE_INVOICE_DESCRIPTION = (
    "{label} subscription: daily credit limit of {limit}, unlimited media sends, unlimited voice calls, "
    "Gender and Country based search, Privacy Mode access, partner details on match, and {points} bonus points."
)
SUBSCRIBE_PAYMENT_SUCCESS_TEXT = (
    "✅ <b>{label} plan activated!</b>\n\n"
    "<i>Active until:</i> <code>{expires}</code>\n\n"
    "<b>+{points}</b> points added to your account 🎉\n\n"
    "Daily credit limit is now <b>{limit}</b> — and your voice calls & media sends are now unlimited."
)
SUBSCRIBE_GROUP_DM_SENT_TEXT = "📩 <b>{user_tag}</b>, <i>I have sent the VIP subscription tiers to your private DM!</i>"
SUBSCRIBE_GROUP_START_DM_TEXT = "⚠️ <b>{user_tag}</b>, <i>please start the bot in private DM first so I can send the VIP tiers!</i>"

# ---------------------------------------------------------------------------
# subscription.py status texts
# ---------------------------------------------------------------------------
SUBSCRIPTION_STATUS_FREE_TEXT = (
    "<i>Account Status:</i> <b>{badge} {label}</b>\n"
    "<i>Daily voice calls:</i> <b>{rem_calls}/{call_limit} remaining today</b>\n"
    "<i>Daily matches:</i> <b>{credit_limit} chats/day</b>"
)
SUBSCRIPTION_STATUS_VIP_TEXT = (
    "✅ <b>{badge} {label}</b> <i>plan active</i> — <i>{time_left_str}</i>\n"
    "<i>Daily credit limit:</i> {credit_limit} chats/day "
    "(voice calls & media sends are free & unlimited on your plan)"
)

# ---------------------------------------------------------------------------
# commands/prune.py
# ---------------------------------------------------------------------------
PRUNE_NOT_IN_CHAT = "⚠️ <b>You are not currently in an active chat.</b>\n\nUse /find to connect with someone!"
PRUNE_USAGE = (
    "💡 <b>Two-Way Wipe (/prune):</b>\n\n"
    "<i>Reply to any message (yours or your partner's) with</i> <code>/prune</code> "
    "<i>to permanently erase it for both of you!</i>"
)
PRUNE_UPGRADE_PROMPT = (
    "🔒 <b>Two-Way Wipe (/prune) is a VIP Feature!</b>\n\n"
    "<i>Permanently erase any message for both you and your partner with zero trace.\n"
    "Unlocked instantly on all VIP plans (starting at 25 ⭐ / ₹20).</i>"
)

# ---------------------------------------------------------------------------
# commands/call.py
# ---------------------------------------------------------------------------
CALL_NOT_IN_CHAT_TEXT = "⚠️ <b>You must be in an active chat to start a call.</b>\n\nUse /find to match with someone first!"
CALL_ALREADY_ACTIVE_TEXT = "📞 <b>A voice call is already active in this session.</b>"
CALL_LIMIT_REACHED_TEXT = (
    "⚠️ <b>Daily Voice Call Limit Reached</b> ({used}/{limit})\n\n"
    "Free accounts can make up to <b>3 voice calls per day</b> (resets at midnight UTC).\n"
    "Upgrade to VIP with /subscribe to unlock <b>unlimited voice calls</b>, priority matching, and exclusive perks!"
)
CALL_INCOMING_TEXT = (
    "📞 <b>Incoming Anonymous Voice Call!</b>\n\n"
    "<i>Your partner is inviting you to talk directly via private voice call.</i>\n"
    "🔒 <b>100% Anonymous:</b> Private audio room with zero account IDs or IP addresses shared."
)
CALL_CALLING_PARTNER_TEXT = "📞 <b>Calling partner...</b>\n\n<i>Waiting for them to accept your call request...</i>"
CALL_INVITATION_EXPIRED_TEXT = "⏳ <b>Call invitation expired.</b>"
CALL_DECLINED_TEXT = "❌ <b>Call declined.</b>"
CALL_PARTNER_DECLINED_TEXT = "ℹ️ <b>Your partner declined the voice call.</b>"
CALL_SESSION_ENDED_TEXT = "⚠️ <b>Chat session ended before call connected.</b>"
CALL_CONNECTED_RECV_TEXT = "🎉 <b>Call Connected!</b>\n\nTap below to open the secure audio room:"
CALL_CONNECTED_INIT_TEXT = "🎉 <b>Partner accepted the call!</b>\n\nTap below to join the audio room:"
CALL_ENDED_TEXT = "🛑 <b>Voice call ended.</b>"
CALL_PARTNER_ENDED_TEXT = "🛑 <b>Your partner ended the voice call.</b>"

# ---------------------------------------------------------------------------
# commands/help.py
# ---------------------------------------------------------------------------
HELP_GROUP_REDIRECT_TEXT = "💡 <b>Open the bot in private DM to use all features!</b>"

# ---------------------------------------------------------------------------
# commands/admin_commands.py - /giveaway
# ---------------------------------------------------------------------------
GIVEAWAY_USAGE_TEXT = (
    "<i>Usage:</i> <code>/giveaway &lt;user_id&gt; &lt;tier&gt;</code>\n\n"
    "<i>Tier is one of:</i> <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"
)
GIVEAWAY_UNKNOWN_TIER_TEXT = "<i>Unknown tier.</i> Use one of: <code>daily</code>, <code>weekly</code>, <code>monthly</code>, <code>yearly</code>"

# ---------------------------------------------------------------------------
# media_privacy.py / relay.py
# ---------------------------------------------------------------------------
PRIVATE_MODE_SUBSCRIBERS_ONLY_TEXT = (
    "🔒 <b>Privacy Mode is a subscriber perk.</b>\n\n"
    "Your media will be sent as a normal message instead. Use /subscribe to unlock Privacy Mode."
)
MEDIA_DAILY_LIMIT_REACHED_TEXT = (
    "📷 <b>You've used all of your daily credits, so this {kind} wasn't sent.</b>\n\n"
    "Your credits reset at midnight UTC, or /subscribe for unlimited media sends."
)

# ---------------------------------------------------------------------------
# commands/games.py
# ---------------------------------------------------------------------------
NEED_PARTNER_FOR_GAME_TEXT = "<b>You need a partner first.</b>\n\nUse /find to get matched up!"
PICK_GAME_TEXT = "🎮 <b>Pick a game to challenge your partner to:</b>"
SENDING_GAME_REQUEST_TEXT = "⏳ <b>Sending your game request...</b>"

# ---------------------------------------------------------------------------
# commands/help.py
# ---------------------------------------------------------------------------
HELP_TEXT = (
    "📖 <b>Chat Zone — Help Menu</b>\n\n"
    "<blockquote>🎯 <b>Chatting & Matching</b>\n"
    "/start — <i>Show the welcome message</i>\n"
    "/find — <i>Find a new chat partner</i>\n"
    "/next — <i>Skip to the next partner</i>\n"
    "/stop — <i>End the current conversation</i>\n"
    "/nudge — <i>Nudge your partner if they've gone quiet</i>\n"
    "/status — <i>Check your partner's connection status</i>\n"
    "/block — <i>Block partner from matching with you again</i></blockquote>\n\n"
    "<blockquote>❤️ <b>Social & Connections</b>\n"
    "/friendreq — <i>Add partner to Anonymous Friends</i>\n"
    "/friends — <i>Open your friends list & reconnect</i>\n"
    "/link — <i>Share your Telegram profile button</i>\n"
    "/gift — <i>Send a gift to your partner</i>\n"
    "/profile — <i>View & customize your profile and badge</i>\n"
    "/leaderboard — <i>Weekly top chatters leaderboard</i></blockquote>\n\n"
    "<blockquote>🌐 <b>VIP & Interactive Tools</b>\n"
    "/subscribe — <i>VIP passes, Stars & Direct checkout</i>\n"
    "/prune — <i>Erase replied message for both users (VIP)</i>\n"
    "/call — <i>Start private 1-on-1 voice call</i>\n"
    "/games — <i>Challenge partner to a mini-game</i>\n"
    "/private — <i>Send media with view protection</i>\n"
    "/help — <i>Show this help menu</i></blockquote>\n\n"
    "───\n"
    "🧰 <b>Support:</b> <a href=\"{admin_url}\">@AdminSupport</a>\n"
    "💬 <b>Community:</b> <a href=\"https://t.me/groupchatzone\">@groupchatzone</a>\n"
    "📢 <b>Updates:</b> <a href=\"https://t.me/channelofchatzone\">@channelofchatzone</a>"
)

# ---------------------------------------------------------------------------
# commands/admin_commands.py
# ---------------------------------------------------------------------------
GIVE_BROADCAST_MESSAGE_TEXT = "<b>Give me a message to broadcast!</b>"
GIVE_VALID_CONNECT_USER_ID_TEXT = "<b>Give me a valid user id to connect.</b>\n\n<i>Usage:</i> <code>/connect &lt;user_id&gt;</code>"
TARGET_NOT_IN_DB_TEXT = "<b>The target user isn't in our database.</b>"
ALREADY_CONNECTED_TO_TARGET_TEXT = "<b>You are already connected to the target.</b>"

ADMIN_HELP_TEXT = (
    "<b>Admin commands:</b>\n"
    "• <code>/stats</code> — <i>Bot user and performance statistics</i>\n"
    "• <code>/queue</code> — <i>Queue and matchmaking status</i>\n"
    "• <code>/checkuser &lt;user_id&gt;</code>\n"
    "• <code>/ban &lt;user_id&gt; &lt;severity 0-10&gt; [reason]</code>\n"
    "• <code>/unban &lt;user_id&gt;</code>\n"
    "• <code>/giveaway &lt;user_id&gt; &lt;tier&gt;</code>\n"
    "• <code>/referral &lt;required_referrals&gt; &lt;promo_duration_days&gt;</code>\n"
    "• <code>/broadcast &lt;message&gt;</code>\n"
    "• <code>/campaign</code> — <i>Manage sponsor promotions</i>\n"
    "• <code>/connect &lt;user_id&gt;</code>"
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
    "<i>Usage:</i> <code>/referral &lt;required_referrals&gt; &lt;promo_duration_days&gt; [reward_days]</code>\n\n"
    "<i>e.g.</i> <code>/referral 10 30 2</code> — refer 10 friends, get 2 days VIP, promo active for 30 days.\n\n"
    "<i>To turn it off:</i>\n\t<code>/referral 0 0</code>"
)
REFERRAL_DISABLED_TEXT = "🛑 <b>Referral scheme turned off.</b>"

# ---------------------------------------------------------------------------
# commands/stop.py
# ---------------------------------------------------------------------------
CHAT_ENDED_TEXT = "👋 <b>Chat ended.</b>"
REMOVED_FROM_QUEUE_TEXT = "❗ <b>You've been removed from the waiting queue.</b>\n\nUse /find to search for a partner."
NOT_IN_CHAT_TEXT = "❗ <b>You're not in a chat.</b>"

# ---------------------------------------------------------------------------
# handlers/rating.py
# ---------------------------------------------------------------------------
RATE_PROMPT_TEXT = "💡 <b>If your chat partner misbehaved or broke the rules, report them below.</b>\n\nYou can also rate them, which affects their profile rating."
REPORT_REASON_PROMPT_TEXT = "🚩 <b>What happened?</b> Pick the closest reason:"
REPORT_LOGGED_TEXT = "✅ <b>Thanks, we've logged that report.</b>\n\nYour feedback helps keep this bot safe."
FEEDBACK_THANKS_TEXT = "<b>Thank you for your feedback.</b>\n\nIt helps keep everyone here safe."

# ---------------------------------------------------------------------------
# handlers/preferences.py
# ---------------------------------------------------------------------------
PREFERENCES_INTRO_FIRST_TIME_TEXT = (
    "🏷️ <b>Pick what you're into — this helps us match you with people who share your vibe.</b>\n\n"
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
SETUP_PROFILE_GENDER_PROMPT_TEXT = "<b>Let's set up your profile.</b>\n\nWhat's your gender?"
SELECT_GENDER_TEXT = "<b>Please select your gender:</b>"
ENTER_AGE_TEXT = "📅 <b>Please enter your age:</b>"
INVALID_AGE_TEXT = "❌ <b>Please enter a valid age.</b>"
PREFERENCES_BUTTONS_NUDGE_TEXT = "🏷️ <b>Let us know your preferences</b>\n\nUse the buttons above to pick your interests, then hit <b>Done</b>."

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
NOT_IN_CHAT_USE_FIND_INLINE_TEXT = "❗ <b>You're not in a chat.</b>\n\nUse /find to connect."

LINK_RESTRICTED_TEXT = (
    "🔒 <b>Links and usernames cannot be shared in chat.</b>\n\n"
    "• <i>To share your profile safely, use</i> /link\n\n"
    "• <i>Or upgrade to VIP with</i> /subscribe <i>to send links freely!</i>"
)
MEDIA_WARMUP_LOCKED_TEXT = (
    "⏳ <b>Media sharing unlocks after the first 90 seconds of chat.</b>\n\n"
    "<i>Available in</i> <b>{remaining}s</b> <i>(or buy a subscription with</i> /subscribe <i>to send immediately).</i>"
)
LINK_COMMAND_WARMUP_LOCKED_TEXT = (
    "⏳ <b>Profile sharing unlocks after the first 90 seconds of chat.</b>\n\n"
    "<i>Available in</i> <b>{remaining}s</b> <i>(or buy a subscription with</i> /subscribe <i>to share anytime).</i>"
)
LINK_NO_USERNAME_TEXT = (
    "⚠️ <b>You don't have a Telegram username set!</b>\n\n"
    "<i>To share your profile safely, you must set a username in your Telegram settings:</i>\n"
    "1. Open Telegram <b>Settings</b>\n"
    "2. Tap <b>Edit Profile</b> → <b>Username</b>\n"
    "3. Set a username, then try /link again!"
)
LINK_SENT_TO_PARTNER_ALERT = "🔗 <b>Your chat partner shared their Telegram profile with you!</b>"
LINK_SENT_SUCCESS_TEXT = "✅ <i>Your profile link has been shared with your partner.</i>"

# ---------------------------------------------------------------------------
# media_privacy.py
# ---------------------------------------------------------------------------
SENT_PRIVACY_MODE_TEXT = "🔒 <i>Sent in <b>Privacy Mode</b>.</i>\n\nIt'll be gone once they've seen it."
PRIVACY_MODE_PLACEHOLDER_TEXT = "🔒 <b>Privacy Mode media</b>\n\nIt disappears after you open it."
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
ALREADY_IN_GAME_TEXT = "<b>You're already in a game.</b>\n\nFinish that first or use /cancel to cancel the currently running game."
PARTNER_ALREADY_IN_GAME_TEXT = "<b>Your partner is already in a game.</b>\n\nLet them finish first."
CANT_SPAM_GAME_REQUESTS_TEXT = "<b>You can't just spam requests and expect your partner to accept it 💀.</b>"
WAITING_FOR_PARTNER_ACCEPT_TEXT = "⏳ <b>Waiting for your partner to accept...</b>"
GAME_REQUEST_EXPIRED_TEXT = "<b>This request expired or doesn't exist.</b>"
YOU_DECLINED_REQUEST_TEXT = "<b>You declined the request.</b>"
PARTNER_DECLINED_REQUEST_TEXT = "<b>Your partner has declined the request.</b>"

# ---------------------------------------------------------------------------
# Shared across multiple mini-games (games/coin_steal.py, rps.py, tictactoe.py,
# guess_it.py, would_you_rather.py)
# ---------------------------------------------------------------------------
PARTNER_LEFT_GAME_TEXT = "<b>Your partner left the game.</b>\n\nGame ended..."
GAME_ENDED_INACTIVITY_TEXT = "<b>Game ended due to inactivity.</b>"
WON_MATCH_TEXT = "🏆 <b>You won the match!</b> +8 points."
LOST_MATCH_TEXT = "😔 <b>You lost the match.</b> Rematch sometime?"

# ---------------------------------------------------------------------------
# commands/cancel.py
# ---------------------------------------------------------------------------
GAME_CANCELLED_TEXT = "🛑 <b>Game cancelled.</b>\n\nYour chat is still open, use /games to start another."
GAME_REQUEST_CANCELLED_TEXT = "🛑 <b>Game request cancelled.</b>"
PARTNER_CANCELLED_REQUEST_TEXT = "<b>Your partner cancelled the game request.</b>"
NOTHING_TO_CANCEL_TEXT = "<b>You don't have an active game or pending game request to cancel.</b>"

# ---------------------------------------------------------------------------
# games/coin_steal.py
# ---------------------------------------------------------------------------
ALREADY_CHOSE_TEXT = "<b>You already chose.</b> Chill 😭"
CHOICE_LOCKED_IN_TEXT = "<b>Your choice has been locked in 🔒.</b>"
OPPONENT_MOVED_TEXT = "<b>Your opponent made their move...</b> Do you trust them? 👀"
MUTUAL_SAVE_NO_STREAK_TEXT = "<b>You guys really trusted each other!</b> 👀\n\nGood job saving your coins for now 😏"
BOTH_STOLE_TEXT = "<b>Both chose greed over the other and stole.</b>\n\nNow no one wins 😏."
GOT_STOLEN_FROM_TEXT = "<b>You shouldn't have done that to them 💀.</b>\n\nThey tried to save their coin and you just stole it..."
TRUSTED_WRONG_ONE_TEXT = "<b>You sure trusted the wrong one this time 💀.</b>\n\nYou just got stolen..."
COIN_STEAL_END_INTRO_TEXT = "<b>The game has come to an end.</b>\n\nWell played both of you.\n\n"
WON_BY_DECEIVING_TEXT = "<b>You really won by deceiving them 💔.</b>"
LOST_TRUST_LESSON_TEXT = "<b>Maybe that's why they tell us not to trust anyone on the internet 🥀.</b>"
COIN_STEAL_DRAW_TEXT = "<b>You guys managed to make it a draw 👏.</b>\n\nWell played for sure!"
COIN_STEAL_TIMEOUT_TEXT = "<b>Game ended due to inactivity.</b>\n\nRestart if you guys wanna play again."

# ---------------------------------------------------------------------------
# games/rps.py
# ---------------------------------------------------------------------------
OPPONENT_ALREADY_PICKED_TEXT = "<b>Your opponent already picked.</b>\n\nYour move..."

# ---------------------------------------------------------------------------
# games/tictactoe.py
# ---------------------------------------------------------------------------
DRAW_NOTE_TEXT = "\n\n🤝 <b>It's a draw!</b>\n\nWell played both of you."
GAME_OVER_NOTE_TEXT = "\n\n🏆 <b>Game over!</b>"
