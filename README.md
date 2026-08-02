# 💬 AnonChatZoneBot

An anonymous chat bot for Telegram that pairs strangers — by shared interests when possible — for real-time private conversations, with a moderation system, Privacy Mode media, and a handful of mini-games to play with your partner.

---

## What's new in this rework

- **Interest-based matching** — pick tags (Gaming, Anime, Flirting, Music, Movies, Sports, Memes, Relationships, Study, Politics) and `/find` tries to pair you with someone who shares them, falling back to FIFO after a short grace period so nobody waits forever.
- **Severity-based moderation** — reports now ask *why*, each reason carries a weight, and crossing a threshold auto-restricts the offender for a duration scaled to severity (0–10), quietly and automatically — no admin has to be paged for every report that comes in. Thresholds are scaled deliberately high so a single report (even a serious one) never restricts someone on its own; it takes a real, sustained pattern of reports. Admins can also manually `/ban`, `/unban`, and `/checkuser`.
- **Admins can't be restricted, ever** — not manually, not automatically, not even by themselves. `/ban`-ing yourself (or another admin) is explicitly blocked, and the automatic report-threshold system skips admin accounts entirely.
- **Full lockout while restricted** — a restricted user can't run any command, tap any button, or send any message until their restriction expires (or an admin lifts it). If someone thinks a restriction is a mistake, they reach out to an admin themselves to get it reviewed.
- **Privacy Mode media, now opt-in** — sending a photo/video/voice/video note relays instantly like anything else *unless* you caption it `/private` (or send a bare `/private` first, then the media right after within 5 minutes). Either way it's then held server-side, delivered with forward/save protection, and deleted from the chat shortly after your partner opens it — photos after a flat 45s, videos/voice/video notes after their own duration plus that same 45s so playback never gets cut off. See [Privacy note on Privacy Mode media](#privacy-note-on-privacy-mode-media) for what this can and can't guarantee.
- **Consistent profile editing** — editing your gender, age, country, or interests from `/profile` now always drops you back into the profile menu afterward, instead of just ending. Same flow everywhere, no dead ends.
- **HTML formatting everywhere** — every message the bot sends uses Telegram's HTML parse mode instead of Markdown, and anything derived from user input (report reasons, ban reasons, etc.) is escaped before being sent. This was the main source of "can't parse entities" failures in the old version and should no longer happen.
- **More mini-games** — Coin Steal (reworked with trust streaks and a wildcard round), Tic Tac Toe, Rock Paper Scissors, Guess It, and Would You Rather — all available via `/games`.

Spam detection (a lightweight in-memory rate limiter) has been removed — it added a small delay to every single update for very little practical benefit. The restriction system (via reports and manual admin action) remains as the actual moderation layer.

---

## How It Works

Users start the bot, set up a quick profile (gender, age, country, and optional interest tags), then use `/find` to enter a waiting queue. The bot pairs them up — preferring someone who shares interests — and relays messages between them in real time. Neither user ever sees the other's Telegram ID or username.

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
├── saveNload.py                # PostgreSQL save/load layer
├── security.py                 # Safe Telegram API wrapper, restriction gate, error handler
│
├── commands/
│   ├── start.py / find.py / next.py / stop.py / help.py / profile.py / games.py
│   └── admin_commands.py       # /broadcast, /connect, /ban, /unban, /checkuser
│
├── handlers/
│   ├── setup.py                # New user onboarding flow (decorator + handler)
│   ├── gender.py / country.py / edit.py
│   ├── preferences.py          # Interest tag toggle menu (bitmask storage)
│   └── rating.py               # Post-chat rating + reason-based reporting
│
├── games/
│   ├── registry.py             # Tracks which game each user is in, for cleanup on disconnect
│   ├── game_requests.py        # Generic request/accept/decline flow for all games
│   ├── coin_steal.py / tictactoe.py / rps.py / guess_it.py / would_you_rather.py
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

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message; triggers profile setup for new users |
| `/find` | Join the waiting queue, matched by shared interests when possible |
| `/next` | Skip current partner, rate them, and search for a new one |
| `/stop` | End the current chat and rate your partner |
| `/help` | Show all available commands |
| `/profile` | View/edit your profile and interests |
| `/games` | Pick a mini-game to challenge your partner to |
| `/coinsteal` | Quick-start a Coin Steal game request |
| `/private` | Arm Privacy Mode, then send your media right after (or just caption the media `/private` directly) |

**Admin only (not shown in `/help` or the bot's command menu):** `/broadcast <message>`, `/connect <user_id>`, `/ban <user_id> <severity 0-10> [reason]`, `/unban <user_id>`, `/checkuser <user_id>`

---

## Moderation system

Reports go through a reason picker (spam, rude/toxic, unwanted NSFW, harassment, scam, leaked private media, underage concern), each adding weighted points to the target's `severity_score`. Crossing a threshold auto-computes a ban severity (0–10) and restricts the user for a duration scaled to that severity — from a few minutes up to long-term. This all happens silently: no message is sent to the owner when a report comes in or a restriction triggers. Restricted users are told why they're restricted and can reach out to an admin themselves if they think it's a mistake — admins can look up the full report history with `/checkuser`. `severity_score` decays slowly over time so a couple of old minor reports don't follow someone around forever.

`restricted_until` is `NULL` when a user isn't restricted, and a timestamp otherwise. A restricted user is blocked at the very first stage of update processing, before any command or button handler runs, so *everything* is locked, not just chat.

Admin accounts (the owner and anyone in `ADMIN_IDS`) can never be restricted — not through `/ban` (including on yourself), and not automatically through reports, no matter how many pile up.

---

## Privacy note on Privacy Mode media

Sending a photo/video/voice/video note while paired relays normally by default. Caption it `/private` (or send a bare `/private` command first, then the media within 5 minutes) and it goes out in Privacy Mode instead. Once opened, the bot sends it with `protect_content` (blocks forward/save in stock Telegram clients) and deletes its own copy shortly after — 45s for photos, or the media's own duration plus 45s for video/voice/video notes, so playback never gets cut off mid-way. What this **can't** guarantee: once media is delivered to a device, that device has it — a modified client can still retain a file it already downloaded, and Telegram gives bots no visibility into screenshots. That's true of every bot on the platform, not something fixable in code. The report system's "leaked my private media" reason (high severity) is the real backstop for misuse, not a technical promise.

---

## Mini-games

All playable via `/games` (or `/coinsteal` directly for that one) between two currently paired users. Whoever leaves the chat mid-game auto-forfeits and their partner is notified — no orphaned sessions.

- **Coin Steal 🪙** — 3-round trust game, Save or Steal each round, streak bonuses for repeated mutual trust, wildcard round 3.
- **Tic Tac Toe ⭕❌** — classic, first to three in a row.
- **Rock Paper Scissors 🪨📄✂️** — best of 5.
- **Guess It 🔢** — alternating number-guessing duel with hot/cold hints, best of 3.
- **Would You Rather 🤔** — 5-round compatibility duel, prompts pulled from your shared interest tags when possible, ends with a match percentage.

---

## Database

Same `user_details` table as before, extended with: `preferences` (bitmask int), `restricted_until`, `restriction_reason`, `severity_score`, `report_log` (JSONB), `last_severity_decay`. New columns are added automatically on startup via `ALTER TABLE ... IF NOT EXISTS`, so upgrading an existing deployment doesn't need a manual migration.

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
