# 💬 AnonChatZoneBot

An anonymous chat bot for Telegram that randomly pairs strangers for real-time private conversations — built entirely for the love of the game. No third-party storage, no accounts, just two people matched together through Telegram.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Features](#features)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Commands](#commands)
- [User Profile & Setup](#user-profile--setup)
- [Rating & Reporting System](#rating--reporting-system)
- [Coin Steal Game](#coin-steal-game)
- [Admin Controls](#admin-controls)
- [Database](#database)
- [Error Handling](#error-handling)

---

## How It Works

Users start the bot, set up a quick profile (gender, age, country), then use `/find` to enter a waiting queue. Once two users are queued, the bot pairs them and relays all messages between them in real time — neither user ever sees the other's Telegram ID or username. When done, they rate each other and move on.

All message relay happens server-side. The bot forwards text, photos, videos, audio, voice notes, video notes, stickers, GIFs, and documents between partners transparently.

---

## Features

### Anonymous Matching
- Random partner matching from a shared waiting queue
- Partner's rating (👍/👎) is shown when a match is made
- `/next` skips the current partner and immediately queues for a new one

### Message Relay
Supports relaying all major Telegram message types between partners:
- Text messages
- Photos (with caption)
- Videos (with caption)
- Video notes (round videos)
- Voice messages
- Audio files (with caption)
- Documents (with caption)
- Stickers
- Animations / GIFs (with caption)

### User Profiles
- Each user sets up gender, age, and country on first use
- Profile fields are editable at any time via `/profile`
- Profile data persists across bot restarts via PostgreSQL

### Rating & Reporting
- After every conversation ends, both users are prompted to rate their partner (👍 or 👎)
- Users can also report a partner for misconduct (🚩)
- A `feedback_track` system prevents double-voting and double-reporting within the same session
- Feedback tracks are cleared every 8 hours to prevent data bloat

### Points System
- Users earn points by playing the Coin Steal game
- Points are stored per user in the database

### Coin Steal Game
- A 3-round psychological game playable with your current chat partner
- Each round: both players simultaneously choose to **Save** or **Steal**
- Round 3 applies a x2 multiplier if one player saves and the other steals
- Winner earns 10 points; draws and timeouts earn 1 point each
- Games time out after 5 minutes of inactivity

### Data Persistence
- User data is saved to PostgreSQL every 60 seconds (dirty-write pattern — only changed users are written)
- Data is also flushed on clean shutdown

### Admin Controls
- `/broadcast` — sends a message to every registered user
- `/connect <user_id>` — forcibly pairs the admin with a specific user (disconnects their existing partners gracefully and is used to investigate users with abnormal amount of reports)

---

## Project Structure

```
AnonChatZoneBot/
├── main.py                     # App entry point, handler wiring, periodic jobs
├── app.py                      # Flask keep-alive server (for cloud deployment)
├── init.py                     # Global state: waiting queue, active pairs, user details
├── relay.py                    # Message relay logic between paired users
├── saveNload.py                # PostgreSQL save/load layer
├── security.py                 # Safe Telegram API wrapper, global error handler
│
├── commands/
│   ├── start.py                # /start — welcome message
│   ├── find.py                 # /find — queue and match users
│   ├── next.py                 # /next — skip partner, re-queue
│   ├── stop.py                 # /stop — end current chat
│   ├── help.py                 # /help — command reference
│   ├── profile.py              # /profile — show and edit user profile
│   └── admin_commands.py       # /broadcast, /connect (owner only)
│
├── handlers/
│   ├── setup.py                # New user onboarding flow (decorator + handler)
│   ├── gender.py               # Gender selection callback handler
│   ├── country.py              # Country selection menu + callback handler
│   ├── edit.py                 # Profile edit callback handler
│   ├── rating.py               # Post-chat rating and report handler
│   └── coin_steal_game.py      # Coin Steal game request/accept/decline handler
│
├── games/
│   └── coin_steal.py           # Coin Steal game logic, session management, timeout
│
├── requirements.txt
└── Procfile
```

---

## Tech Stack

- **Python 3** — core language
- **python-telegram-bot v20+** — async Telegram Bot API wrapper (with job-queue)
- **Flask** — lightweight web server for keep-alive pings on cloud platforms
- **PostgreSQL** — persistent user data storage via `psycopg2`
- **Procfile** — Railway / Heroku compatible deployment config

---

## Requirements

- Python 3.10+
- A PostgreSQL database (local or hosted, e.g. Railway, Supabase, Neon)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

### Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` includes:
```
python-telegram-bot
python-telegram-bot[job-queue]
Flask
nest_asyncio
aiofiles
psycopg2-binary
```

---

## Configuration

All configuration is done via **environment variables**.

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Telegram bot token from BotFather |
| `OWNER` | ✅ | Your Telegram user ID (for admin commands and error reports) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string (e.g. `postgresql://user:pass@host/db`) |

### Example `.env`

```env
BOT_TOKEN=123456:ABC-DEF...
OWNER=987654321
DATABASE_URL=postgresql://user:password@localhost:5432/anonchat
```

---

## Running the Bot

```bash
python main.py
```

On startup the bot will:
1. Connect to PostgreSQL and create the `user_details` table if it doesn't exist
2. Load all existing user data into memory
3. Restore any previously active partner pairings
4. Start the Flask keep-alive server on port `8080`
5. Begin polling for Telegram updates

### Deploying to Railway

1. Push the project to a GitHub repository
2. Create a new Railway project and connect the repository
3. Add a PostgreSQL plugin (Railway auto-sets `DATABASE_URL`)
4. Add `BOT_TOKEN` and `OWNER` as environment variables
5. Railway uses the `Procfile` (`web: python3 main.py`) to start the bot automatically

---

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message; triggers profile setup for new users |
| `/find` | Join the waiting queue and get matched with a partner |
| `/next` | Skip current partner, rate them, and immediately search for a new one |
| `/stop` | End the current chat and rate your partner |
| `/help` | Show all available commands |
| `/profile` | View your profile and edit gender, age, or country |
| `/coinsteal` | Challenge your current chat partner to a game of Coin Steal |

---

## User Profile & Setup

New users are automatically walked through a setup flow on their first interaction:

1. **Gender** — inline button selection (Male / Female)
2. **Age** — free text input (validated as integer)
3. **Country** — inline button selection from a menu of 10 countries + "Other"

All three fields must be completed before a user can use `/find`. The setup flow is enforced via the `@check_user_profile` decorator applied to every command handler.

After setup, users can edit any field at any time via `/profile`:
- Editing gender and country shows the same inline button menus
- Editing age prompts for a new text input

---

## Rating & Reporting System

After every chat ends (via `/stop` or `/next`), both users receive a feedback prompt:

- 👍 **Upvote** — increases the partner's positive rating
- 👎 **Downvote** — increases the partner's negative rating
- 🚩 **Report** — logs a report against the partner

A `feedback_track` dictionary prevents any user from voting or reporting the same partner more than once per session. The feedback track for all users is automatically cleared every **8 hours** to keep memory usage in check.

When a new partner is found, their current rating (total upvotes and downvotes) is shown to both users immediately upon matching.

---

## Coin Steal Game

A 3-round game of trust and betrayal playable between two currently paired users.

### How to play
1. Either partner sends `/coinsteal` — a game request is sent to the other partner
2. The partner accepts or declines via inline buttons
3. Each round, both players simultaneously and independently choose:
   - **Save 🤝** — cooperate with your partner
   - **Steal 😈** — take their coin

### Scoring

| Player 1 | Player 2 | P1 Score | P2 Score |
|---|---|---|---|
| Save | Save | +1 | +1 |
| Steal | Steal | +0 | +0 |
| Steal | Save | +2 | +0 |
| Save | Steal | +0 | +2 |

**Round 3 only:** If one player saves and the other steals, the stealer earns **+4** instead of +2 (x2 multiplier).

### End of game
- **Winner** (higher score after 3 rounds): +10 points
- **Draw**: no points awarded
- **Timeout** (5 minutes of inactivity): both players get +1 point and the game ends

Games are session-based (UUID) and fully cleaned up after completion or timeout.

---

## Admin Controls

Available only to the user whose Telegram ID matches the `OWNER` environment variable.

### `/broadcast <message>`
Sends the given message to every registered user in the database. Rate-limited to one message per user per 0.1 seconds to avoid hitting Telegram's flood limits.

### `/connect <user_id>`
Forcibly pairs the admin with the specified user. Handles all edge cases:
- Disconnects the target user from their current partner (if any)
- Disconnects the admin from their current partner (if any)
- Sends disconnection notices and rating prompts to all displaced partners
- Establishes the new pair and notifies both users
- `Important` : This command is only for the owner of the bot and is used to investigate questionable activities the bot

---

## Database

User data is stored in a single PostgreSQL table:

```sql
CREATE TABLE user_details (
    user_id        BIGINT PRIMARY KEY,
    gender         VARCHAR(1),
    age            INTEGER,
    country        VARCHAR(25),
    reports        INTEGER,
    reporters      TEXT,           -- JSON array of reporter user IDs
    vote_up        INTEGER,
    vote_down      INTEGER,
    voters         TEXT,           -- JSON array of voter user IDs
    feedback_track JSONB,          -- per-session vote/report tracking
    partner_id     BIGINT,         -- current partner (NULL if not in chat)
    points         INTEGER
);
```

### Write strategy

The bot uses a **dirty-write pattern** to minimise database load. When a user's data changes, their ID is added to the `dirty_users` set. The periodic save job (every 60 seconds) only writes users in that set, then clears it. Data is also flushed on clean shutdown via the `post_shutdown` hook.

---

## Error Handling

All Telegram API calls go through `safe_tele_func_call`, which silently catches `Forbidden` errors (the user blocked the bot) and returns `None` instead of raising an exception.

A global error handler (`global_error_handler`) catches all unhandled exceptions during update processing and sends a formatted error report directly to the owner's DM, including:
- Exception type and message
- User ID that triggered the error
- The file, line number, function name, and source line of the innermost non-library stack frame

`Conflict` errors (multiple bot instances running) and "message is not modified" `BadRequest` errors are silently ignored.