# 💬 AnonChatZoneBot (v2.0 Scalable Architecture)

An enterprise-ready, anonymous chat bot for Telegram engineered to handle **500,000+ users** with high concurrency, transactional PostgreSQL storage (3NF baseline), robust matchmaking, silent chat preservation, multi-layer ban/block enforcement, data-driven mini-games, and a sponsors/promotions engine.

---

## 🌟 Key Capabilities & Upgrades

1. **Silent Chat Guarantee**:
   - **Silence ≠ Disconnection**: Two users who remain silent in an active chat will stay connected indefinitely. Inactivity timers are eliminated.
   - Genuine transport disconnects (e.g. user blocking the bot in Telegram) are caught proactively via `TelegramError` (`Forbidden`) and cleanly terminated without ghost sessions or crashes.
2. **PostgreSQL 3NF Database & Data Migration**:
   - Redesigned from a monolithic text table (`user_details`) into normalized 3NF relational tables (`users`, `user_profiles`, `user_blocks`, `user_reports`, `user_ratings`, `chat_sessions`, `subscriptions`, `payment_transactions`, `referrals`, `bot_config`, `promotions`, `game_questions`).
   - Atomic zero-data-loss migration module (`migrations.py`) that safely migrates legacy user records into normalized tables and preserves legacy tables as `legacy_user_details_backup`.
   - Sized `AsyncConnectionPool` (`DB_POOL_MIN=5`, `DB_POOL_MAX=30`) preventing connection starvation under high concurrency.
3. **Multi-Layer Ban & Block Enforcement**:
   - Banned or blocked users can never enter the waiting queue, remain in queue, or be matched.
   - Enforced at 4 separate layers: (1) Queue entry, (2) Real-time restriction triggers, (3) Candidate filtering during matching, and (4) Pre-match atomic check.
   - Dynamic user-to-user blocking via `/block` or post-chat inline buttons (`rateblock|<id>`) with 24-hour block duration (blocks automatically expire after 24 hours).
4. **Scalability for 500,000+ Users**:
   - No O(N) memory scans at startup or on timer ticks. Daily severity score decay is computed in O(1) inside PostgreSQL via `UPDATE ... RETURNING`.
   - Thread-safe matchmaking using `asyncio.Lock` preventing duplicate matches or race conditions.
   - In-memory working cache with dirty-tracking flushing to PostgreSQL via parameterized batch operations.
5. **Data-Driven Games Engine**:
   - **Would You Rather**: Extracted from hardcoded arrays into data-driven JSON / database content (`games/content/wyr_questions.json` & `game_questions` table) supporting categories (General, Deep, Fun, Dating, Moral) and dynamic random selection.
   - **Trivia Duel (New Game)**: 5-round interactive multiplayer trivia battle with instant scoring, multiple choice options, and clean forfeit handling.
   - Extensible base game framework decoupled from the core chat relay.
6. **Sponsors & Promotions Engine**:
   - Native campaign system supporting priority scheduling, configurable display frequency, cooldowns, impressions, and click tracking.
   - Non-intrusive post-chat promo delivery with inline URL buttons.
   - Full admin control via `/campaign` command (add, pause, activate, delete, stats).
7. **Production Observability & Security**:
   - Health check HTTP endpoint (`GET /health`) with live metrics (active sessions, queue size, pool status, uptime).
   - Anti-spam per-user rate limiting token bucket.
   - OWNER error alert throttling (max 1 notification per 15s) preventing Telegram flood/ban during API issues.
   - HTML injection immunity and 100% parameterized SQL queries.
8. **In-Bot Anonymous Friends List (`/friends`, `/friendreq`)**:
   - Save connections to an internal list without revealing Telegram usernames or phone numbers.
   - Tiered capacity (16 base for free, +16 slots per subscription tier).
   - Automatic Roman numeral deduplication (`Bestie I`, `Bestie II`).
   - Paginated card viewer with Nickname/Note editing, Favorite pinning, mutual friend removal, and busy-aware connect invites.
9. **The 60-Second "Accidental Skip" Undo Button**:
   - Allows users who accidentally skipped via `/next` to immediately reconnect with their previous partner within 60 seconds.
10. **100% Privacy & VIP Gender Peek**:
   - Zero public profile or bio leakage. Regular chats remain strictly anonymous.
   - Exclusive VIP/subscriber perk: discreet partner gender notification at match start.
11. **"Save Our Conversation" (Transcript Export)**:
   - Clean, 100% anonymized `.txt` conversation memory delivered to Saved Messages upon chat conclusion.
12. **Anonymous WebApp Voice Calling (`/call`)**:
   - Private 1-on-1 audio rooms launched via Telegram WebApp (WebRTC) with zero Telegram ID or IP address exposure.
13. **Native Emoji Reactions & Chat Action Mirroring**:
   - Bidirectional relay of native Telegram emoji reactions and real-time chat actions (`typing...`, `recording voice...`).

---

## 🏗️ Project Architecture

```
AnonChatZoneBot/
├── main.py                     # Bot startup, lifecycle hooks, and periodic jobs
├── app.py                      # Flask server + GET /health endpoint for cloud monitoring
├── init.py                     # Global state, queue primitives, bitmask interest definitions
├── migrations.py               # 3NF PostgreSQL DDL, composite indexes, and data migration
├── saveNload.py                # Transactional DB operations & connection pool (AsyncConnectionPool)
├── session_manager.py          # Chat session lifecycle, silent chat preservation, transport drops
├── matchmaking.py              # Interest-based pairing, FIFO sweep, multi-layer ban/block filter
├── relay.py                    # Message relay with rate-limiting, dice, and Privacy Mode media
├── moderation.py                # Severity scoring, auto-restriction, eviction triggers, SQL decay
├── media_privacy.py             # Atomic view-once media revelation
├── subscription.py             # Telegram Stars subscriptions, tier stacking, atomic credit consumption
├── referral.py                  # Referral scheme with multi-tier reward accumulation
├── security.py                 # Rate limiting, throttled error reporter, safe Telegram API call wrapper
│
├── commands/
│   ├── start.py / find.py / next.py / stop.py / cancel.py / help.py / profile.py / games.py
│   ├── block.py                # User-to-user blocking command (/block)
│   ├── nudge.py                # Partner presence ping (/nudge) and status checker (/status)
│   └── admin_commands.py       # /broadcast, /connect, /ban, /unban, /checkuser, /giveaway, /stats, /queue, /campaign
│
├── handlers/
│   ├── setup.py                # Profile onboarding flow
│   ├── gender.py / country.py / edit.py
│   ├── preferences.py          # Interest tag toggle menu (bitmask storage)
│   ├── payments.py             # Telegram Stars invoice & pre-checkout handlers
│   └── rating.py               # Post-chat rating, reason-based reporting, and instant blocking
│
├── games/
│   ├── registry.py             # Active game registry & disconnect teardown
│   ├── game_requests.py        # Generic request/accept/decline challenge flow with TTL
│   ├── would_you_rather.py     # Data-driven Would You Rather engine
│   ├── trivia.py               # 5-Round Trivia Duel mini-game engine
│   ├── coin_steal.py / tictactoe.py / rps.py / guess_it.py
│   └── content/
│       ├── content_manager.py  # Content loader from JSON seed files & PostgreSQL
│       ├── wyr_questions.json  # Seed questions for Would You Rather
│       └── trivia_questions.json # Seed questions for Trivia Duel
│
├── promotions/
│   └── service.py              # Campaign engine, cooldowns, impressions, and post-chat delivery
│
├── tests/                      # Automated test suite (pytest + pytest-asyncio)
│   ├── test_database.py        # DDL & constraint verification
│   ├── test_matchmaking.py     # Concurrent matchmaking, bans, blocks, and fairness
│   ├── test_sessions.py        # Silent chat preservation, transport drops, duplicate prevention
│   ├── test_moderation.py      # Severity scoring, auto-escalation, admin immunity
│   ├── test_games.py           # Would You Rather & Trivia Duel question loading and state
│   ├── test_promotions.py      # Campaign cooldowns, impressions, and display logic
│   ├── test_security.py        # Rate limiting, anti-spam, HTML escaping, subscription stacking
│   └── test_presence.py        # Nudge, status command, and official channel broadcast tests
│
├── requirements.txt            # Pinned production dependencies
└── Procfile                    # Deployment process configuration
```

---

## 🗄️ Database Schema (3NF Baseline)

The database uses PostgreSQL with foreign key constraints, cascade triggers, and partial indexes:

- **`users`**: Core user record (`user_id` PK, `gender`, `age`, `country`, `preferences_bitmask`, `points`, `created_at`, `updated_at`).
- **`user_profiles`**: Volatile user states (`severity_score`, `restricted_until`, `restriction_reason`, `daily_credits_used`, `daily_credits_reset_day`, `is_banned`).
- **`user_blocks`**: User-to-user blocking table (`blocker_id`, `blocked_id`, `created_at`) with unique constraint and 24-hour expiration window.
- **`user_reports`**: Moderation audit trail (`reporter_id`, `target_id`, `reason_code`, `weight`, `created_at`).
- **`user_ratings`**: Up/down karma feedback (`voter_id`, `target_id`, `vote_type`, `created_at`).
- **`chat_sessions`**: Session audit history (`id` UUID PK, `user1_id`, `user2_id`, `started_at`, `ended_at`, `end_reason`).
- **`subscriptions`**: Stars subscriptions (`user_id`, `tier`, `starts_at`, `expires_at`, `source`, `is_active`).
- **`payment_transactions`**: Stars payment audit log (`telegram_payment_charge_id` UNIQUE).
- **`referrals`**: Referral link tracking with idempotency (`referred_id` UNIQUE).
- **`bot_config`**: Dynamic key-value configuration (`key` PK, `value` JSONB).
- **`promotions`**: Sponsor campaigns (`title`, `sponsor_name`, `message_text`, `button_text`, `button_url`, `priority`, `impressions_count`, `clicks_count`, `is_active`).
-**`game_questions`**: Data-driven question repository (`game_type`, `category`, `prompt_a`, `prompt_b`, `correct_answer`).
- **`user_friends`**: Anonymous friends network (`id` PK, `user_id`, `friend_id`, `custom_name`, `notes`, `is_favorite`, `created_at`).

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | - | Telegram Bot API token from `@BotFather` |
| `OWNER` | ✅ | - | Telegram user ID of the primary owner/admin |
| `DATABASE_URL` | ✅ | - | PostgreSQL connection URI (`postgresql://user:pass@host:5432/dbname`) |
| `ADMIN_IDS` | ❌ | `""` | Comma-separated list of secondary admin IDs (e.g. `123,456`) |
| `PORT` | ❌ | `8080` | Port for the Flask health-check server |
| `DB_POOL_MIN` | ❌ | `5` | Minimum connection pool size |
| `DB_POOL_MAX` | ❌ | `30` | Maximum connection pool size |
| `ANNOUNCEMENT_CHANNEL` | ❌ | - | Official Telegram Channel (`@Channel` or `-100...`) for instant broadcast |
| `LOCAL_BOT_API_URL` | ❌ | - | Base URL for self-hosted Telegram Bot API server (enables 2GB media & high speed) |

---

## 🚀 Local Development & Setup

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.12)
- PostgreSQL 14+ (local or hosted, e.g., Supabase / Neon / Render)

### 2. Installation
```bash
git clone https://github.com/jishnuharis/AnonChatZoneBot.git
cd AnonChatZoneBot

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install pinned dependencies
pip install -r requirements.txt
```

### 3. Configure Environment
Create a `.env` file in the project root:
```env
BOT_TOKEN=123456789:ABCDefghIJKlmNoPQRsTUVwxyZ
OWNER=987654321
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/anonchat
PORT=8080
```

### 4. Run Migrations & Start Bot
Migrations execute automatically on startup during `init_pool()`:
```bash
python main.py
```

### 5. Running the Test Suite
The automated test suite runs offline without requiring a live Telegram connection or active PostgreSQL database:
```bash
python -m pytest -v
```
All 32 tests will run and validate matchmaking, sessions, silent chat, games, promotions, moderation, presence, security, and paid match filters.

---

## ⭐ Paid Subscriber Match Filters (Gender & Country Preferences)

Paid users with active Telegram Stars subscriptions unlock custom matchmaking criteria:

- **Configure in Profile**: Navigate to `/profile` and click **"⭐ Match Filters (Gender/Country)"**.
- **Gender Preference**:
  - `Any Gender`: Connect with anyone regardless of gender.
  - `Male Only (M)`: Connect exclusively with male partners.
  - `Female Only (F)`: Connect exclusively with female partners.
- **Country Preference**:
  - `Any Country`: Connect with users worldwide.
  - `Same Country Only`: Pair only with users registered with the same country as you.
- **Mutual Compatibility**: If both users are subscribed, the matchmaking engine enforces both criteria symmetrically before forming a chat.
- **VIP Queue Priority**: Paid candidates receive a scoring boost (`+100`) over neutral zero-overlap free pairings, ensuring subscribers are matched first.
- **Paywall Protection**: Free users can inspect the menu and are presented with an upgrade prompt with subscription tiers (`/subscribe`).

---

## 🎮 Games & Content Expansion

### How to Add More "Would You Rather" Questions
1. Edit `games/content/wyr_questions.json` and append your question:
   ```json
   {
     "category": "fun",
     "a": "Always speak in rhymes",
     "b": "Sing everything you say"
   }
   ```
2. Or insert directly into the database:
   ```sql
   INSERT INTO game_questions (game_type, category, prompt_a, prompt_b)
   VALUES ('wyr', 'deep', 'Know how you will die', 'Know when you will die');
   ```

### Trivia Duel Mini-Game
- Challenge partner via `/games` or `/trivia`.
- Both players receive 5 randomized multiple-choice trivia questions.
- Answers are scored in real time with an inline summary at the end.

---

## 📢 Sponsors & Promotions Management

Admins can manage sponsor promotions live without modifying bot code:

- **Create a campaign**:
  ```
  /campaign add <title> | <sponsor> | <priority> | <message> | [button_text] | [button_url]
  ```
- **List active campaigns**:
  ```
  /campaign list
  ```
- **Pause a campaign**:
  ```
  /campaign pause <id>
  ```
- **View impression & click statistics**:
  ```
  /campaign stats
  ```

---

## 👥 Partner Presence & Interaction Indicators

AnonChatZoneBot v2.0 features real-time presence indicators to eliminate ghosting anxiety and keep conversations engaging:

- **Docked Typing Area Keyboard**: When paired, a persistent `ReplyKeyboardMarkup` docks directly below the typing input with `["👋 Nudge", "⏱️ /status"]` and `["/next", "/stop"]`. Cleanly unmounted on chat exit.
- **"👋 Nudge" Button & `/nudge` Command**: Gentle ping with a 15-second anti-spam cooldown that sends a notification (`"👋 *NUDGE!* Your partner is nudging you!"`) and triggers typing actions on the partner's screen.
- **`/status` Command**: Displays partner connection status and relative last activity (`Active right now`, `25s ago`, `2m ago`).
- **Dynamic Media Chat Actions**: Automatically sends native Telegram chat actions (`upload_photo`, `upload_video`, `record_voice`, `record_video_note`, `upload_document`, `typing`) as media relays, keeping partners visually aware while media transfers.

---

## 🛡️ Admin & Operational Commands

| Command | Permission | Description |
|---|---|---|
| `/stats` | Admin | Real-time bot metrics (users, active chats, queue, memory) |
| `/queue` | Admin | Inspect queue contents, waiting times, and active counts |
| `/campaign` | Admin | Manage sponsor promotions and view conversion stats |
| `/broadcast <msg>` | Admin | Post to `ANNOUNCEMENT_CHANNEL` instantly (1 API call) or use `/broadcast direct <msg>` for batch PMs |
| `/ban <id> <sev> [reason]` | Admin | Apply moderation restriction (severity 0-10) |
| `/unban <id>` | Admin | Lift restriction and unban user immediately |
| `/checkuser <id>` | Admin | View detailed user record, reports, and rating history |
| `/giveaway <id> <tier>` | Admin | Grant complimentary Stars subscription tier |
| `/connect <id>` | Owner | Force-pair with target user for support/testing |

---

## 📊 Cloud Deployment

### Health Check Endpoint
The built-in web server exposes `GET /health` which returns JSON:
```json
{
  "status": "healthy",
  "active_chats": 142,
  "queue_length": 8,
  "loaded_users": 1530,
  "pool_ready": true,
  "uptime_seconds": 86400
}
```
Use this endpoint with keep-alive services (e.g. UptimeRobot, Render Health Check, Koyeb, AWS ALB).

---

## 📄 License
MIT License. Created for AnonChatZoneBot.