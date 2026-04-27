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

```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<YOUR_DOMAIN>/webhook/telegram&secret_token=<WEBHOOK_SECRET>"
```

For local development the bot uses polling (no webhook needed).

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | From @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | — | Random secret for webhook validation |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `OLLAMA_BASE_URL` | — | Ollama server URL |
| `OLLAMA_MODEL` | — | Default: `qwen2.5:7b` |
| `USDA_API_KEY` | — | From api.nal.usda.gov |
| `SENTRY_DSN` | — | Sentry error tracking |
| `VOICE_PROCESSING_ENABLED` | — | Default: `true` |
| `MAX_VOICE_SECONDS` | — | Default: `120` |

---

## Ollama Setup

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull model
ollama pull qwen2.5:7b

# Or add ollama service to docker-compose.yml for self-hosted
```

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
  utils/       Units, text numbers, fuzzy matching
alembic/       DB migrations
scripts/       Seed scripts + backup
tests/         pytest test suite
```

---

## Tests

```bash
# Install deps locally
pip install -r requirements.txt

# Run tests
pytest

# Run specific test file
pytest tests/test_units.py -v
```

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
