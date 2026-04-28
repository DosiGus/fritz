# Fritz — Telegram Nutrition Tracker

Track meals in natural language via Telegram. Send a text or voice message, Fritz calculates macros.

## Setup

### 1. Clone and configure

```bash
cp .env.example .env
# Fill in: TELEGRAM_BOT_TOKEN, USDA_API_KEY, SENTRY_DSN (optional)
```

### 2. Start services

```bash
docker compose up -d
```

### 3. Run migrations

```bash
docker compose exec app alembic upgrade head
```

### 4. Seed data

```bash
docker compose exec app python scripts/seed_default_foods.py
docker compose exec app python scripts/seed_food_aliases.py
docker compose exec app python scripts/seed_portion_rules.py
```

### 5. Set Telegram webhook (production)

Telegram allows exactly one update mechanism per bot token. Choose one of:

- **Polling** (default, used in `docker compose up` via the `bot` service). Leave `BOT_WEBHOOK_MODE=false` and don't set a webhook.
- **Webhook**: set `BOT_WEBHOOK_MODE=true` in `.env`, **stop the `bot` service** (e.g. comment it out in `docker-compose.yml` or run only `app` and `worker`), and register the webhook below. The FastAPI `app` service then receives updates and routes them through the bot Application.

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<YOUR_DOMAIN>/webhook/telegram&secret_token=<WEBHOOK_SECRET>"
```

For local development the bot uses polling (no webhook needed).

### Production compose

The default `docker-compose.yml` is optimized for local development. For VPS/beta use, layer the production file on top:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Production compose removes source-code mounts and `uvicorn --reload`, runs `alembic upgrade head` before app/bot/worker startup, adds container restart policies, and checks app readiness through `/ready`.

Run a manual DB backup through the ops profile:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml --profile ops run --rm db-backup
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `APP_ENV` | — | `development`, `production`, etc. |
| `APP_NAME` | — | Service name in FastAPI/logs |
| `LOG_LEVEL` | — | Python root log level, defaults to `INFO` |
| `ADMIN_TOKEN` | ✅ production | Required for all `/admin` endpoints via `X-Admin-Token` |
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | — | Random secret for webhook validation |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `OLLAMA_BASE_URL` | — | Ollama server URL |
| `OLLAMA_MODEL` | — | Default: `qwen2.5:7b` |
| `OPENAI_API_KEY` | ✅ voice | Required for OpenAI voice transcription |
| `OPENAI_TRANSCRIPTION_MODEL` | — | Default: `gpt-4o-transcribe` |
| `OPENAI_TRANSCRIPTION_TIMEOUT` | — | Default: `60` seconds |
| `USDA_API_KEY` | — | From api.nal.usda.gov |
| `SENTRY_DSN` | — | Sentry error tracking |
| `VOICE_PROCESSING_ENABLED` | — | Default: `true` |
| `MAX_VOICE_SECONDS` | — | Default: `120` |

---

## Ollama Setup

Docker Compose includes an `ollama` service. After the stack is running, pull the configured model once:

```bash
docker compose up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b
```

Keep `OLLAMA_BASE_URL=http://ollama:11434` when the app runs inside Docker. If you run the FastAPI app directly on your Mac and install Ollama locally, use `OLLAMA_BASE_URL=http://localhost:11434` instead.

---

## Project Structure

```
app/
  bot/         Telegram handlers, commands, keyboards
  api/         FastAPI routes (health, admin, webhooks)
  db/          SQLAlchemy models + repositories
  schemas/     Pydantic schemas
  services/    Business logic and Nutrition Intelligence Engine
  integrations/ HTTP clients (Open Food Facts, USDA, Ollama, Telegram)
  workers/     RQ worker + voice jobs
  utils/       Units, text numbers, fuzzy matching, rate_limit
alembic/       DB migrations
scripts/       Seed scripts + backup
tests/         pytest test suite
```

---

## Tests

```bash
# Install deps locally
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_units.py -v

# Run voice job tests (all mocked — no Whisper binary needed)
pytest tests/test_voice_jobs.py -v

# Run rule parser tests
pytest tests/test_rule_parser.py -v

# Run gold-standard engine tests
pytest tests/test_goldstandard_engine.py -v
```

---

## Admin API

All admin endpoints are under `/admin` and require the `X-Admin-Token` header to match `ADMIN_TOKEN`. If `ADMIN_TOKEN` is empty, the Admin API returns `503` to avoid accidental public exposure.

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/admin/stats
curl -X POST -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/admin/sentry-test
```

### Overview endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/admin/stats` | User count, logs today, audit events today |
| GET | `/admin/metrics` | Full operational dashboard: errors, abort rates, pending reviews |
| GET | `/admin/users` | List users (supports `limit`, `offset`) |
| GET | `/admin/top-foods` | Most logged foods by canonical name |
| GET | `/admin/unknown-foods` | Most frequent unknown foods from audit events |
| GET | `/admin/failed-logs` | Logs with status `failed` or `pending_confirmation` |
| GET | `/admin/api-errors` | Recent persisted Open Food Facts / USDA request errors |
| GET | `/admin/llm-errors` | Recent LLM parser errors from audit events |
| GET | `/admin/voice-errors` | Recent voice processing errors from audit events |
| GET | `/admin/nutrition-reviews` | Unknown-food review queue from `nutrition_review_needed` |
| GET | `/admin/nutrition-items` | List nutrition cache items (`verified=false` to filter unverified) |
| GET | `/admin/food-aliases` | List food aliases |
| GET | `/admin/audit-events` | Recent audit events (filter with `event_type=...`) |

### Action endpoints

| Method | Path | Body | Description |
|---|---|---|---|
| POST | `/admin/food-aliases` | `{alias, canonical_name, language?, confidence?}` | Add a food alias |
| POST | `/admin/portion-rules` | `{unit_text, food_name?, default_grams?, default_kcal?, ...}` | Add a portion rule |
| POST | `/admin/nutrition-items/{id}/verify` | — | Mark a nutrition item as verified |
| POST | `/admin/nutrition-reviews/{id}/resolve` | `{resolution?, note?, canonical_name?, alias?, kcal_100g?, protein_100g?, carbs_100g?, fat_100g?}` | Resolve unknown-food review and optionally create verified nutrition data |
| POST | `/admin/sentry-test` | — | Protected Sentry smoke event; returns `503` when `SENTRY_DSN` is missing |

Admin write actions create `admin_action` audit events. If a nutrition review is resolved with a `canonical_name` but no explicit `alias`, Fritz creates an alias from the reviewed unknown item so the same user phrase can match automatically next time.

When a user logs a food with a known amount but no nutrition match, Fritz does not save a `0 kcal` log. It creates a `nutrition_review_needed` event and asks the user to send a better-known alternative name; the next message reuses the original amount and runs through the normal nutrition pipeline.

### Metrics response (`GET /admin/metrics`)

```json
{
  "failed_logs": 3,
  "pending_reviews": 5,
  "nutrition_match_failed_today": 2,
  "nutrition_reviews_open": 4,
  "nutrition_reviews_resolved": 1,
  "api_errors_today": 1,
  "llm_errors_today": 0,
  "voice_errors_today": 0,
  "clarification_asked_total": 40,
  "clarification_resolved_total": 32,
  "clarification_open_total": 8,
  "clarification_abort_rate": 0.2
}
```

---

## Voice Worker

Voice messages are processed asynchronously via an RQ worker.

**Worker setup:**

```bash
# Start worker (inside Docker or locally with Redis running)
docker compose exec worker rq worker nutrition-voice nutrition-jobs

# Or locally:
rq worker --url redis://localhost:6379/0 nutrition-voice nutrition-jobs
```

**How voice logging works:**

1. User sends a voice message in Telegram.
2. Bot downloads the file and pushes a job to the Redis `nutrition-voice` queue.
3. Bot immediately replies with "Processing…" so the user is not blocked.
4. Worker picks up the job and transcribes audio through OpenAI `gpt-4o-transcribe`.
5. Transcript is passed through the same food pipeline as text messages.
6. Bot sends the result (saved log or clarification question, including inline buttons) back to the user.
7. Temporary audio file is deleted after processing (success or failure).

The worker sends the Telegram audio file to OpenAI's transcription API with `language=de` and a nutrition-specific prompt to reduce food-word mistakes.

**Voice configuration:**

| Setting | Default | Description |
|---|---|---|
| `VOICE_PROCESSING_ENABLED` | `true` | Toggle voice support on/off |
| `OPENAI_API_KEY` | — | Required when voice support is enabled |
| `OPENAI_TRANSCRIPTION_MODEL` | `gpt-4o-transcribe` | OpenAI transcription model |
| `OPENAI_TRANSCRIPTION_TIMEOUT` | `60` | OpenAI transcription timeout in seconds |
| `MAX_VOICE_SECONDS` | `120` | Max allowed voice message length |
| `VOICE_TMP_DIR` | `/tmp/voice` | Temp directory for audio files |

The worker logs `transcription_error` and sends a user-facing failure message when `OPENAI_API_KEY` is missing or the transcription request fails.

---

## API Request Logging

Calls to Open Food Facts and USDA FDC are logged at DEBUG level with structured fields (`service`, `endpoint`, `method`, `status_code`, `success`, `duration_ms`). Errors are logged at WARNING level. Calls made from the DB-backed nutrition matcher are also stored in `api_request_logs`.

Rate limiters are active by default:

| Client | Rate limit |
|---|---|
| Open Food Facts | 10 requests / 60 s |
| USDA FDC | 10 requests / 60 s |

The `api_request_logs` database table stores request history persistently for matcher calls that have a database session (added in migration `0002`).

---

## Backup

```bash
# Manual backup
PGPASSWORD=postgres bash scripts/backup_db.sh

# Add to cron (daily at 3am)
0 3 * * * PGPASSWORD=postgres BACKUP_DIR=/backups bash /app/scripts/backup_db.sh
```

---

## Services

| Service | Port | Description |
|---|---|---|
| FastAPI app | 8000 | REST API + webhooks |
| Telegram bot | — | Polling or webhook mode |
| RQ worker | — | Voice jobs + nutrition jobs |
| PostgreSQL | 5432 | Main database |
| Redis | 6379 | Job queue |

---

## Nutrition Intelligence Engine

Implemented modules:

- `app/services/rule_parser.py` — rule-based German food extraction
- `app/services/llm_parser.py` — Ollama-based structure-only fallback parsing
- `app/services/parser_merge.py` — Rule/LLM merge logic with hallucination guard
- `app/services/portion_engine.py` — gram/ml/default-kcal resolution and options
- `app/services/confidence_engine.py` — confidence aggregation and decisions
- `app/services/nutrition_matcher.py` — cache, alias, fuzzy, default and API matching
- `app/services/clarification_service.py` — persisted inline-button state machine
- `app/services/user_memory_service.py` — personal portion lookup and recording
- `app/services/meal_template_service.py` — template save/log support
- `app/services/food_pipeline.py` — end-to-end `handle_food_message()` orchestration

---

## Beta-Test / Production Checklist

Before going live with real users, verify the following:

### Infrastructure

- [ ] PostgreSQL running with daily automated backup (cron `scripts/backup_db.sh`)
- [ ] Redis running and accessible to worker
- [ ] RQ worker running (`nutrition-voice`, `nutrition-jobs` queues)
- [ ] Sentry DSN configured and receiving test events
- [ ] Telegram webhook set to HTTPS production URL
- [ ] `TELEGRAM_WEBHOOK_SECRET` set and matching webhook config

### Configuration

- [ ] `APP_ENV=production` in `.env`
- [ ] `TELEGRAM_BOT_TOKEN` is the production bot token (not a test bot)
- [ ] `USDA_API_KEY` set (USDA requests will fail or use demo key otherwise)
- [ ] `OPEN_FOOD_FACTS_USER_AGENT` includes contact email
- [ ] `OLLAMA_BASE_URL` points to running Ollama instance with model pulled
- [ ] `VOICE_PROCESSING_ENABLED=true` and `OPENAI_API_KEY` set

### Data

- [ ] All seed scripts run: `seed_default_foods`, `seed_food_aliases`, `seed_portion_rules`
- [ ] Migrations applied (`alembic upgrade head`, currently through `0003`)
- [ ] `ADMIN_TOKEN` set and kept out of source control

### Smoke Tests

- [ ] `GET /health` returns 200
- [ ] `GET /ready` returns 200 and reports database + Redis ready
- [ ] `GET /admin/stats` returns 200
- [ ] Send `/start` to bot — user created in DB
- [ ] Send `250g Skyr` to bot — log saved, macros returned
- [ ] Send voice message to bot — processing message received, result returned
- [ ] `/today` shows correct daily summary

### Monitoring

- [ ] `GET /admin/metrics` checked and all counters are sensible
- [ ] Sentry receives at least one protected smoke event (`POST /admin/sentry-test`)
- [ ] Log aggregation set up (or structured logs visible in `docker compose logs`)
