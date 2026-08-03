# 💬 AnonChatZoneBot

An anonymous chat bot for Telegram that pairs strangers — by shared interests when possible — for real-time private conversations, with moderation, Privacy Mode media, mini-games, and an optional Stars subscription for power users.

---

## How It Works

Users start the bot, set up a quick profile (gender, age, country, and optional interest tags), then use `/find` to enter a waiting queue. The bot pairs them up — preferring someone who shares interests — and relays messages between them in real time. Neither user ever sees the other's Telegram ID or username.

---

## Features

- **Interest-based matching** — pick tags (Gaming, Anime, Flirting, Music, Movies, Sports, Memes, Relationships, Study, Politics) and `/find` tries to pair you with someone who shares them, falling back to FIFO after a short grace period so nobody waits forever.
- **Full-duplex message relay** — text, stickers, photos, videos, GIFs, voice notes, video notes, and emoji reactions all relay live between partners.
- **Mini-games** — play Coin Steal, Tic Tac Toe, Rock Paper Scissors, Guess It, or Would You Rather with your partner via `/games`.
- **Privacy Mode media** — a subscriber perk. Photos/videos/voice/video notes sent while paired relay normally by default; captioning the media `/private` (or sending a bare `/private` first, then the media within 5 minutes) sends it with forward/save protection instead, and the bot deletes its own copy shortly after your partner opens it.
- **Daily credit system** — every account gets a shared daily pool of credits (reset at midnight UTC) that covers `/next` skips for everyone and photo/video/voice/video note sends for free-tier users. Subscribers get a larger pool and send all media free of charge.
- **Stars subscriptions** — `/subscribe` sells Daily/Weekly/Monthly/Yearly plans via native Telegram Stars payments, granting a higher daily credit limit, unlimited free media sends, Privacy Mode access, seeing your partner's age/gender/country on match, and bonus in-bot points.
- **Referral program** — grab your personal invite link anytime from the 🔗 button on `/profile`. When an admin-configured promo is running, getting enough friends to join through it and finish setting up their profile earns you a free subscription, repeatable each time you clear the threshold — the bot occasionally mentions this right after a chat ends, too.
- **Severity-based moderation** — reports ask *why*, each reason carries a weight, and crossing a threshold auto-restricts the offender for a duration scaled to severity (0–10) — no admin has to be paged for every report. Admins can also manually `/ban`, `/unban`, and `/checkuser`.
- **Admins can't be restricted, ever** — not manually, not automatically, not even by themselves.
- **Full lockout while restricted** — a restricted user can't run any command, tap any button, or send any message until their restriction expires or an admin lifts it.
- **Consistent profile editing** — editing your gender, age, country, or interests from `/profile` always drops you back into the profile menu afterward.
- **HTML formatting everywhere** — every message the bot sends uses Telegram's HTML parse mode, and anything derived from user input (report reasons, ban reasons, etc.) is escaped before being sent.

---

## Project Structure

```
AnonChatZoneBot/
├── main.py                     # App entry point, handler wiring, periodic jobs
├── app.py                      # Flask keep-alive server (for cloud deployment)
├── init.py                     # Global state: queue, active pairs, user details, preference tags
├── relay.py                    # Message relay + Privacy Mode media interception
├── matchmaking.py              # Interest-aware pairing + FIFO fallback sweep
├── moderation.py                # Report reasons, severity scoring, ban/restrict logic
├── media_privacy.py             # Privacy Mode media flow
├── subscription.py             # Stars subscription tiers, daily credit limits
├── referral.py                  # Referral scheme, link generation, crediting & rewards
├── saveNload.py                # PostgreSQL save/load layer
├── security.py                 # Safe Telegram API wrapper, restriction gate, error handler
│
├── commands/
│   ├── start.py / find.py / next.py / stop.py / cancel.py / help.py / profile.py / games.py
│   └── admin_commands.py       # /broadcast, /connect, /ban, /unban, /checkuser, /giveaway
│
├── handlers/
│   ├── setup.py                # New user onboarding flow (decorator + handler)
│   ├── gender.py / country.py / edit.py
│   ├── preferences.py          # Interest tag toggle menu (bitmask storage)
│   ├── payments.py             # Pre-checkout + successful payment handlers (Telegram Stars)
│   └── rating.py               # Post-chat rating + reason-based reporting
│
├── games/
│   ├── registry.py             # Tracks which game each user is in, for cleanup on disconnect
│   ├── game_requests.py        # Generic request/accept/decline flow for all games
│   └── coin_steal.py / tictactoe.py / rps.py / guess_it.py / would_you_rather.py
│
├── tests/                      # Lightweight import + logic sanity checks (no live bot/DB needed)
├── requirements.txt
└── Procfile
```

---

## Configuration

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from BotFather |
| `OWNER` | ✅ | Your Telegram user ID (full admin, error reports) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `ADMIN_IDS` | optional | Comma-separated extra admin user IDs (e.g. `111,222`) |

Telegram Stars payments need no extra provider token or configuration — `/subscribe` uses native Stars invoices (`currency="XTR"`) once the bot has payments enabled in BotFather.

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message; triggers profile setup for new users |
| `/find` | Join the waiting queue, matched by shared interests when possible |
| `/next` | Skip current partner, rate them, and search for a new one |
| `/stop` | End the current chat and rate your partner |
| `/cancel` | Cancel whatever multi-step flow you're currently in (profile setup, editing, etc.) |
| `/help` | Show all available commands |
| `/profile` | View/edit your profile and interests |
| `/games` | Pick a mini-game to challenge your partner to |
| `/coinsteal` | Quick-start a Coin Steal game request |
| `/private` | Send your next photo/video/voice/video note in Privacy Mode (subscriber perk; caption the media `/private` directly, or send it bare first) |
| `/subscribe` | View subscription plans and pay with Telegram Stars |

**Admin only (not shown in `/help` or the bot's command menu):** `/broadcast <message>`, `/connect <user_id>`, `/ban <user_id> <severity 0-10> [reason]`, `/unban <user_id>`, `/checkuser <user_id>`, `/giveaway <user_id> <tier>`

---

## Moderation system

Reports go through a reason picker (spam, rude/toxic, unwanted NSFW, harassment, scam, leaked private media, underage concern), each adding weighted points to the target's `severity_score`. Crossing a threshold auto-computes a ban severity (0–10) and restricts the user for a duration scaled to that severity — from a few minutes up to long-term. This all happens silently: no message is sent to the owner when a report comes in or a restriction triggers. Restricted users are told why they're restricted and can reach out to an admin themselves if they think it's a mistake — admins can look up the full report history with `/checkuser`. `severity_score` decays slowly over time so a couple of old minor reports don't follow someone around forever.

`restricted_until` is `NULL` when a user isn't restricted, and a timestamp otherwise. A restricted user is blocked at the very first stage of update processing, before any command or button handler runs, so *everything* is locked, not just chat.

Admin accounts (the owner and anyone in `ADMIN_IDS`) can never be restricted — not through `/ban` (including on yourself), and not automatically through reports, no matter how many pile up.

---

## Daily credits & subscriptions

Every account draws from a shared daily credit pool (`FREE_DAILY_CREDIT_LIMIT = 32` by default), reset at midnight UTC. `/next` skips draw from this pool for everyone; photo/video/voice/video note sends draw from it too, but only for free-tier users — subscribers send all media free of charge.

`/subscribe` offers four tiers, all paid for with native Telegram Stars (no external payment provider):

| Tier | Duration | Extra daily credits | Stars | Bonus points |
|---|---|---|---|---|
| Daily | 1 day | +16 | 20 ⭐ | 40 |
| Weekly | 7 days | +32 | 70 ⭐ | 150 |
| Monthly | 30 days | +48 | 150 ⭐ | 400 |
| Yearly | 365 days | +64 | 999 ⭐ | 3000 |

Any active plan also unlocks Privacy Mode (`/private`) and shows your partner's age, gender, and country on match. Purchases stack on top of (extend) an existing active subscription rather than overwriting it. Admins can manually grant a tier, with the same perks and bonus points a real purchase would give.

---

## Referral program

Everyone gets a personal invite link, generated on demand via the 🔗 button on `/profile` (also offered, occasionally, right after a chat ends). Share it — when someone joins the bot through your link and finishes setting up their profile (gender, age, country), it counts as a successful referral.

Referrals are only *rewarded* while an admin has a promo running; how many referrals it takes and how long the promo stays live are both admin-configurable. Clearing the threshold grants a free Weekly subscription (stacking on top of any existing plan), and it's repeatable — every time you clear the threshold again while the promo is live, you get another one. Your referral count is never lost even if no promo happens to be running at the time; it's just held until (if) one starts.

---

## Privacy note on Privacy Mode media

Sending a photo/video/voice/video note while paired relays normally by default. Subscribers can caption it `/private` (or send a bare `/private` command first, then the media within 5 minutes) and it goes out in Privacy Mode instead. Once opened, the bot sends it with `protect_content` (blocks forward/save in stock Telegram clients) and deletes its own copy shortly after — 45s for photos, or the media's own duration plus 45s for video/voice/video notes, so playback never gets cut off mid-way. What this **can't** guarantee: once media is delivered to a device, that device has it — a modified client can still retain a file it already downloaded, and Telegram gives bots no visibility into screenshots. That's true of every bot on the platform, not something fixable in code. The report system's "leaked my private media" reason (high severity) is the real backstop for misuse, not a technical promise.

---

## Mini-games

All playable via `/games` (or `/coinsteal` directly for that one) between two currently paired users. Whoever leaves the chat mid-game auto-forfeits and their partner is notified — no orphaned sessions.

- **Coin Steal 🪙** — 3-round trust game, Save or Steal each round, streak bonuses for repeated mutual trust, wildcard round 3.
- **Tic Tac Toe ⭕❌** — classic, first to three in a row.
- **Rock Paper Scissors 🪨📄✂️** — best of 5.
- **Guess It 🔢** — alternating number-guessing duel with hot/cold hints, best of 3.
- **Would You Rather 🤔** — 5-round compatibility duel, prompts pulled from your shared interest tags when possible, ends with a match percentage.

---

## Running the Bot

```bash
pip install -r requirements.txt
python main.py
```

### Running the sanity tests (no live bot/DB required)

```bash
python tests/test_imports.py
python tests/test_logic.py
```