# TODO: Production-Ready Telegram Nutrition Tracker

## 1. Ziel dieser Datei

Diese Datei beschreibt die technische Umsetzung des Telegram Nutrition Trackers. Sie dient als Arbeitsgrundlage für Entwicklung, Sprintplanung und den Coding Agent.

Das Ziel ist keine Hobby-MVP-Version, sondern eine erste ready-to-use Kundenversion für Beta-Tests.

---

## 2. Empfohlener Tech Stack

### Backend

- Python 3.11 oder neuer
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic für Datenbankmigrationen
- PostgreSQL
- Redis
- RQ oder Celery für Worker Jobs
- Docker und Docker Compose

### Telegram

- `python-telegram-bot`
- async Bot Handling
- InlineKeyboardMarkup für Buttons
- Webhook im Production Mode
- Polling nur lokal in Development

### LLM

- Ollama lokal oder auf eigenem Server
- Modell für erste Version:
  - bevorzugt: Qwen 2.5/3 7B oder Llama 3.1/3.2 8B Klasse
  - Alternative: Mistral 7B
- Structured JSON Outputs verwenden
- LLM nur für komplexe Eingaben nutzen
- Rule Parser zuerst ausführen

### Speech-to-Text

- `faster-whisper` oder `whisper.cpp`
- als separater Worker
- Voice-Dateien temporär speichern und nach Verarbeitung löschen
- kein Blocking im Bot-Prozess

### Nutrition APIs

- Open Food Facts
- USDA FoodData Central
- eigener Nutrition Cache
- eigener User-Agent für Open Food Facts
- API Rate Limiting und Caching einbauen

### Monitoring

- Sentry für Exceptions
- strukturierte Logs
- API Request Logs
- Worker Job Logs
- Admin Dashboard Light

### Deployment

Start:

- Docker Compose auf VPS
- PostgreSQL Container oder Managed PostgreSQL
- Redis Container oder Managed Redis
- FastAPI App
- Telegram Bot Service
- Worker Service
- optional separater LLM Server

Später:

- getrennte Services
- horizontale Skalierung der Worker
- separate GPU/CPU Inference Instanz

---

## 3. Projektstruktur

```text
nutrition-tracker/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── logging_config.py
│   │
│   ├── bot/
│   │   ├── telegram_app.py
│   │   ├── handlers.py
│   │   ├── commands.py
│   │   ├── keyboards.py
│   │   └── message_router.py
│   │
│   ├── api/
│   │   ├── routes_health.py
│   │   ├── routes_admin.py
│   │   └── routes_webhooks.py
│   │
│   ├── db/
│   │   ├── session.py
│   │   ├── models.py
│   │   └── repositories/
│   │       ├── users.py
│   │       ├── food_logs.py
│   │       ├── nutrition_items.py
│   │       ├── portions.py
│   │       └── conversation_states.py
│   │
│   ├── schemas/
│   │   ├── parsed_food.py
│   │   ├── nutrition.py
│   │   ├── portions.py
│   │   └── bot_responses.py
│   │
│   ├── services/
│   │   ├── input_preprocessor.py
│   │   ├── rule_parser.py
│   │   ├── llm_parser.py
│   │   ├── portion_engine.py
│   │   ├── confidence_engine.py
│   │   ├── nutrition_matcher.py
│   │   ├── nutrition_calculator.py
│   │   ├── clarification_service.py
│   │   ├── meal_template_service.py
│   │   ├── user_memory_service.py
│   │   ├── summary_service.py
│   │   └── audit_service.py
│   │
│   ├── integrations/
│   │   ├── open_food_facts.py
│   │   ├── usda_fdc.py
│   │   ├── ollama_client.py
│   │   └── telegram_files.py
│   │
│   ├── workers/
│   │   ├── worker.py
│   │   ├── voice_jobs.py
│   │   └── nutrition_jobs.py
│   │
│   └── utils/
│       ├── units.py
│       ├── text_numbers.py
│       ├── fuzzy_matching.py
│       └── time.py
│
├── alembic/
├── scripts/
│   ├── seed_portion_rules.py
│   ├── seed_food_aliases.py
│   └── seed_default_foods.py
│
├── tests/
│   ├── test_rule_parser.py
│   ├── test_portion_engine.py
│   ├── test_confidence_engine.py
│   ├── test_nutrition_matcher.py
│   └── test_clarification_flow.py
│
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── vision.md
├── todo.md
└── README.md
```

---

## 4. Environment Variablen

`.env.example` soll enthalten:

```env
APP_ENV=development
APP_NAME=telegram-nutrition-tracker
BASE_URL=http://localhost:8000

TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=

DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/nutrition
REDIS_URL=redis://redis:6379/0

OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b

OPEN_FOOD_FACTS_USER_AGENT=NutritionTracker/0.1 (contact@example.com)

USDA_API_KEY=

SENTRY_DSN=

VOICE_PROCESSING_ENABLED=true
MAX_VOICE_SECONDS=120
```

---

## 5. Datenbanktabellen

### 5.1 users

```sql
users (
  id uuid primary key,
  telegram_user_id bigint unique not null,
  username text,
  first_name text,
  last_name text,
  language_code text,
  timezone text default 'Europe/Berlin',
  created_at timestamptz not null,
  updated_at timestamptz not null
)
```

### 5.2 user_goals

```sql
user_goals (
  id uuid primary key,
  user_id uuid references users(id),
  daily_calorie_goal integer,
  daily_protein_goal numeric,
  daily_carbs_goal numeric,
  daily_fat_goal numeric,
  active boolean default true,
  created_at timestamptz not null
)
```

### 5.3 food_logs

```sql
food_logs (
  id uuid primary key,
  user_id uuid references users(id),
  raw_text text,
  source text, -- text, voice, template, correction
  meal_type text,
  total_kcal numeric,
  total_protein numeric,
  total_carbs numeric,
  total_fat numeric,
  confidence numeric,
  status text, -- saved, pending_confirmation, corrected, deleted
  logged_at timestamptz not null,
  created_at timestamptz not null
)
```

### 5.4 food_log_items

```sql
food_log_items (
  id uuid primary key,
  food_log_id uuid references food_logs(id),
  original_name text,
  canonical_name text,
  quantity numeric,
  unit text,
  grams numeric,
  kcal numeric,
  protein numeric,
  carbs numeric,
  fat numeric,
  source text,
  source_id text,
  confidence numeric,
  was_estimated boolean default false,
  created_at timestamptz not null
)
```

### 5.5 nutrition_items

```sql
nutrition_items (
  id uuid primary key,
  canonical_name text not null,
  brand text,
  barcode text,
  kcal_100g numeric,
  protein_100g numeric,
  carbs_100g numeric,
  fat_100g numeric,
  source text,
  source_id text,
  verified boolean default false,
  created_at timestamptz not null,
  updated_at timestamptz not null
)
```

### 5.6 food_aliases

```sql
food_aliases (
  id uuid primary key,
  alias text not null,
  canonical_name text not null,
  language text default 'de',
  confidence numeric default 0.8,
  created_at timestamptz not null
)
```

### 5.7 portion_rules

```sql
portion_rules (
  id uuid primary key,
  food_category text,
  food_name text,
  unit_text text not null,
  default_grams numeric,
  min_grams numeric,
  max_grams numeric,
  default_kcal numeric,
  country text default 'DE',
  confidence numeric default 0.7,
  source text,
  created_at timestamptz not null
)
```

### 5.8 user_portion_memory

```sql
user_portion_memory (
  id uuid primary key,
  user_id uuid references users(id),
  phrase text not null,
  food_name text,
  grams numeric,
  ml numeric,
  usage_count integer default 1,
  last_used_at timestamptz,
  created_at timestamptz not null
)
```

### 5.9 meal_templates

```sql
meal_templates (
  id uuid primary key,
  user_id uuid references users(id),
  template_name text not null,
  total_kcal numeric,
  total_protein numeric,
  total_carbs numeric,
  total_fat numeric,
  created_at timestamptz not null,
  updated_at timestamptz not null
)
```

### 5.10 conversation_states

```sql
conversation_states (
  id uuid primary key,
  user_id uuid references users(id),
  state_type text not null,
  payload jsonb not null,
  expires_at timestamptz not null,
  created_at timestamptz not null
)
```

### 5.11 audit_events

```sql
audit_events (
  id uuid primary key,
  user_id uuid,
  event_type text not null,
  payload jsonb,
  created_at timestamptz not null
)
```

---

## 6. Core Pipeline

Implementiere die Hauptpipeline als Service-Methode:

```python
handle_food_message(user_id: UUID, text: str, source: str) -> BotResponse
```

Ablauf:

```text
1. User laden oder erstellen
2. Text normalisieren
3. Prüfen, ob aktiver conversation_state existiert
4. Rule Parser ausführen
5. Wenn Rule Parser Confidence < Threshold, LLM Parser ausführen
6. Parser-Ergebnisse mergen
7. Portion Engine anwenden
8. Nutrition Matcher anwenden
9. Confidence Engine anwenden
10. Entscheidung:
   - direkt speichern
   - als Schätzung speichern
   - Rückfrage stellen
   - Food Match bestätigen lassen
11. Telegram Response erzeugen
12. Audit Event speichern
```

---

## 7. Rule Parser TODOs

- deutsche Zahlen erkennen:
  - eine, ein, einen, zwei, drei, halbe, halb, anderthalb
- Mengenmuster erkennen:
  - `250g`
  - `250 g`
  - `0.5 kg`
  - `500ml`
  - `2 Eier`
  - `1 Banane`
  - `30g Whey`
- mehrere Items in einer Nachricht erkennen:
  - Kommas
  - „und“
  - Zeilenumbrüche
- Einheiten normalisieren:
  - g, gramm → g
  - kg → g
  - ml → ml
  - l → ml
  - stück → piece
  - scheibe → slice
  - el → tbsp
  - tl → tsp
- Confidence pro Item berechnen
- Unit Tests für mindestens 50 typische Eingaben

---

## 8. LLM Parser TODOs

- Ollama Client implementieren
- JSON Schema für Food Extraction definieren
- Timeout setzen
- Retry maximal 1x
- Fallback bei ungültigem JSON
- LLM nur aufrufen, wenn Rule Parser nicht ausreichend ist
- Prompt auf Deutsch und Englisch robust machen
- Output mit Pydantic validieren
- Parser darf keine Kalorien berechnen
- Parser darf keine Nährwerte erfinden

LLM Output Schema:

```json
{
  "meal_type": "unknown|breakfast|lunch|dinner|snack",
  "items": [
    {
      "name": "string",
      "quantity": "number|null",
      "unit": "g|ml|piece|slice|tbsp|tsp|portion|plate|bowl|glass|unknown",
      "preparation": "raw|cooked|fried|grilled|unknown",
      "notes": "string|null"
    }
  ],
  "overall_confidence": "number"
}
```

---

## 9. Portion Engine TODOs

- `portion_rules` aus DB laden
- user-specific `user_portion_memory` bevorzugen
- Standardportionen anwenden
- Portionsgrößenoptionen erzeugen
- Grammwerte ableiten
- Confidence berechnen
- Unklarheiten erkennen
- Rückfragen erzeugen

Initiale Portion Rules seed:

```text
Banane piece 120g
Ei piece 60g
Toast slice 25g
Brot slice 45g
Milch glass 250ml
Haferflocken bowl 80g
Reis gekocht portion 180g
Pasta gekocht plate small 250g
Pasta gekocht plate medium 350g
Pasta gekocht plate large 500g
Döner normal default 650 kcal
Dönerbox Pommes normal default 850 kcal
Chicken Bowl Reis normal default 700 kcal
Chicken Bowl Salat normal default 450 kcal
```

---

## 10. Confidence Engine TODOs

Implementiere Entscheidungsschwellen:

```text
>= 0.85 direct_save
0.70 - 0.84 save_as_estimate
0.50 - 0.69 ask_short_clarification
< 0.50 ask_detailed_clarification
```

Confidence beeinflussen durch:

- exakte Grammangabe
- bekannte Einheit
- bekannter Food Alias
- Nutrition Match Qualität
- Portion Rule Qualität
- User Memory Treffer
- LLM Confidence
- Komplexität der Mahlzeit
- fehlende Zutaten
- mehrdeutige Begriffe

---

## 11. Clarification Flow TODOs

- conversation_state speichern
- Inline Buttons erzeugen
- Callback Handler implementieren
- Antwort des Users auf pending state anwenden
- maximal eine Frage pro Schritt
- State expires after 30 minutes
- Abbruchbefehl unterstützen
- eigene Menge als Freitext erlauben
- nach Korrektur User Memory optional aktualisieren

Typische Clarifications:

```text
portion_size: small/medium/large/custom
meal_variant: rice/chicken, salad/chicken, poke, other
food_match: choose among nutrition matches
custom_amount: user enters grams/ml
save_memory: remember this portion?
```

---

## 12. Nutrition Matcher TODOs

Suchreihenfolge:

```text
1. user-specific foods/templates
2. nutrition_items cache
3. food_aliases → nutrition_items
4. Open Food Facts
5. USDA FoodData Central
6. default generic foods
7. ask user/admin review
```

Implementieren:

- fuzzy matching
- Sprache normalisieren
- cooked/raw unterscheiden
- Markenprodukt vs generisches Produkt unterscheiden
- Open Food Facts Client mit User-Agent
- USDA Client mit API Key
- API Result Caching
- Rate Limiting
- Fehlerbehandlung
- Nutrition Item Verifikation

---

## 13. Voice TODOs

- Telegram Voice Datei herunterladen
- Datei temporär speichern
- Job in Redis Queue legen
- Bot antwortet sofort mit Processing Message
- Worker transkribiert mit faster-whisper oder whisper.cpp
- Transkript an gleiche Text Pipeline geben
- Voice Datei nach Verarbeitung löschen
- Maximaldauer setzen
- Fehlerantwort bei nicht verständlicher Voice Message

---

## 14. Telegram UX TODOs

Commands:

```text
/start
/help
/today
/goal
/delete_last
/edit_last
/favorites
/cancel
```

Freitext-Intents:

```text
Mahlzeit loggen
Tagesstand abfragen
letzten Eintrag löschen
Standardmahlzeit speichern
Standardmahlzeit loggen
Ziele setzen
```

Antwortformat bei erfolgreichem Log:

```text
Gespeichert ✅

Items:
- 250g Skyr
- 1 Banane, geschätzt 120g
- 30g Whey

Gesamt:
438 kcal
52g Protein
42g Carbs
4g Fett

Heute:
1.240 / 2.400 kcal
112 / 180g Protein
```

---

## 15. Admin Dashboard TODOs

Für erste Version genügt ein einfaches FastAPI/Django/Streamlit Admin.

Anzeigen:

- User Count
- Logs Today
- Failed Logs
- Pending Reviews
- häufigste Foods
- häufigste Unknown Foods
- API Errors
- LLM Errors
- Voice Errors
- Clarification Abbruchrate

Actions:

- Food Alias hinzufügen
- Portion Rule hinzufügen
- Nutrition Item verifizieren
- fehlerhaften Log ansehen
- häufige Unknown Foods exportieren

---

## 16. Testing TODOs

Unit Tests:

- Rule Parser
- Text Number Normalization
- Unit Conversion
- Portion Engine
- Confidence Engine
- Nutrition Calculator
- Clarification State Handling

Integration Tests:

- Telegram text message → saved log
- ambiguous meal → clarification state
- button response → saved log
- voice transcript → saved log
- nutrition cache hit
- nutrition API fallback

Testdaten:

- mindestens 100 echte Beispielnachrichten
- deutsche Alltagssprache
- Fitness-Foods
- Restaurant-Foods
- unklare Mengen
- Voice-ähnliche transkribierte Sätze

---

## 17. Sprints

### Sprint 1: Core Backend und Text Logging

Ziel: Text zuverlässig loggen.

Tasks:

- Projektstruktur anlegen
- FastAPI App
- PostgreSQL Setup
- SQLAlchemy Models
- Alembic Migrationen
- Telegram Bot Grundgerüst
- User Erstellung
- Rule Parser v1
- Nutrition Cache v1
- Open Food Facts Client
- USDA Client
- Food Logs speichern
- `/today`
- Tests für Rule Parser

Akzeptanzkriterium:

```text
User kann per Telegram "250g Skyr, 1 Banane, 30g Whey" senden.
Bot speichert Log und antwortet mit Kalorien/Makros.
```

---

### Sprint 2: Portion Intelligence und Confidence

Ziel: Alltagssprache robust verstehen.

Tasks:

- portion_rules Tabelle
- Seed Portion Rules
- food_aliases Tabelle
- Seed Food Aliases
- Portion Engine
- Confidence Engine
- LLM Parser mit Ollama
- Parser Merge Logic
- save_as_estimate Logik
- erste ambiguous meal flows

Akzeptanzkriterium:

```text
"ein Teller Pasta" wird nicht blind gespeichert, sondern mit Portion Buttons geklärt.
"eine Banane" wird mit Standardwert direkt gespeichert.
```

---

### Sprint 3: Clarification Flow und User Memory

Ziel: Bot lernt persönliche Mengen.

Tasks:

- conversation_states
- Telegram Inline Button Handler
- Portion Size Clarification
- Food Match Clarification
- Custom Amount Flow
- User Portion Memory
- Meal Templates
- `/delete_last`
- `/edit_last`
- `/favorites`

Akzeptanzkriterium:

```text
User kann "eine Schüssel Haferflocken" korrigieren auf 80g.
Beim nächsten Mal wird diese Menge automatisch verwendet.
```

---

### Sprint 4: Voice und Worker Architektur

Ziel: Voice Logging produktionsfähig machen.

Tasks:

- Redis
- Worker Setup
- Voice Download
- faster-whisper oder whisper.cpp Integration
- Voice Job Queue
- async Bot Response
- Error Handling
- Voice File Cleanup
- Max Voice Length
- Tests mit Beispieltranskripten

Akzeptanzkriterium:

```text
User sendet Voice Message.
Bot transkribiert, parsed und speichert Mahlzeit oder fragt nach.
```

---

### Sprint 5: Production Ops und Admin

Ziel: Kundentest ermöglichen.

Tasks:

- Docker Compose Production Setup
- Webhook Deployment
- Sentry
- structured logging
- API request logs
- daily DB backup script
- Admin Dashboard light
- error review
- seed scripts
- README Deployment
- Beta Test Checklist

Akzeptanzkriterium:

```text
System läuft 24/7 auf VPS, Logs sind sichtbar, Fehler werden gemeldet, Datenbank wird gesichert.
```

---

## 18. Definition of Done

Eine Funktion gilt erst als fertig, wenn:

- Code implementiert ist
- Pydantic Schemas vorhanden sind
- Fehlerbehandlung implementiert ist
- Logs/Audit Events vorhanden sind
- Tests für Kernlogik geschrieben wurden
- keine API Keys hardcoded sind
- Konfiguration über `.env` läuft
- Bot Response nutzerfreundlich ist
- edge cases berücksichtigt wurden

---

## 19. Technische Prioritäten

Priorität 1:

- Food Logging Pipeline
- Portion Intelligence
- Confidence Engine
- Clarification Flow
- User Memory

Priorität 2:

- Voice
- Admin Dashboard
- Meal Templates
- bessere Food Aliases

Priorität 3:

- Skalierung
- externe Integrationen
- Analytics
- Payments
- Mobile App

---

## 20. Wichtige Architekturentscheidung

Nicht jedes Log darf durch das LLM gehen.

Ablauf muss sein:

```text
Rule Parser zuerst
↓
wenn hohe Confidence: ohne LLM speichern
↓
wenn mittlere/niedrige Confidence: LLM Parser
↓
wenn immer noch unsicher: Rückfrage
```

Das reduziert Kosten, Latenz und Infrastrukturabhängigkeit.
