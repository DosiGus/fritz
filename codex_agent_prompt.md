# Codex Agent Prompt: Build Telegram Nutrition Tracker

## Rolle

Du bist ein senior Python Backend Engineer und Produkt-orientierter AI Engineer. Du setzt einen production-ready Telegram Nutrition Tracker um.

Du darfst nicht nur einen simplen Telegram Bot bauen. Du sollst eine saubere Nutrition Logging Engine mit Portion Intelligence, Confidence Scoring, Clarification Flow und User Memory entwickeln.

Lies zuerst diese Dateien vollständig:

1. `vision.md`
2. `todo.md`

Diese beiden Dateien definieren Produktvision, Architektur, Scope, Sprints, Datenmodell und technische Anforderungen.

---

## Hauptziel

Baue eine erste ready-to-use Kundenversion eines Telegram-basierten Nutrition Trackers.

Der Nutzer soll per Telegram natürliche Sprache oder Voice Messages senden können, zum Beispiel:

```text
250g Skyr, 1 Banane und 30g Whey
```

oder:

```text
Ich hatte einen Teller Pasta mit Tomatensauce
```

Das System soll Lebensmittel und Mengen erkennen, Nährwerte berechnen, bei Unsicherheit kurz nachfragen, persönliche Portionen lernen und Logs speichern.

---

## Wichtigster Produktgrundsatz

Das System darf bei unklaren Mahlzeiten nicht blind raten.

Es muss kontrolliert entscheiden:

```text
direkt speichern
als Schätzung speichern
kurz nachfragen
detailliert nachfragen
```

Diese Entscheidung basiert auf einem Confidence Score.

---

## Architekturvorgabe

Implementiere die Architektur modular.

Pflichtmodule:

```text
Telegram Bot
FastAPI App
PostgreSQL Database
Redis Queue
Worker Service
Rule Parser
LLM Parser
Portion Engine
Confidence Engine
Nutrition Matcher
Clarification Service
User Memory Service
Meal Template Service
Admin Dashboard Light
```

---

## Tech Stack

Nutze:

```text
Python 3.11+
FastAPI
python-telegram-bot
Pydantic v2
SQLAlchemy 2.x
Alembic
PostgreSQL
Redis
RQ oder Celery
Docker Compose
Ollama für lokales LLM
Open Food Facts API
USDA FoodData Central API
faster-whisper oder whisper.cpp für Voice
pytest
```

Wenn du eine Entscheidung treffen musst, wähle die einfachere, robuste und gut testbare Variante.

---

## Projektstruktur

Erstelle diese Struktur:

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
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
├── vision.md
└── todo.md
```

---

## Implementierungsreihenfolge

Arbeite in dieser Reihenfolge. Springe nicht direkt zu Voice oder Admin, bevor die Core Pipeline funktioniert.

### Phase 1: Foundation

1. Projektstruktur erstellen
2. Requirements definieren
3. Docker Compose mit PostgreSQL und Redis
4. FastAPI App mit Health Check
5. Config über `.env`
6. SQLAlchemy Setup
7. Alembic Setup
8. Basismodelle erstellen

### Phase 2: Telegram Text Logging

1. Telegram Bot Setup
2. `/start`, `/help`, `/today`
3. Text Message Handler
4. User automatisch erstellen
5. `handle_food_message()` Pipeline Stub
6. Food Logs speichern

### Phase 3: Rule Parser

1. Text Preprocessor
2. deutsche Zahlen normalisieren
3. Einheiten normalisieren
4. einfache Food Patterns extrahieren
5. Parser Output als Pydantic Schema
6. Tests für typische Eingaben

### Phase 4: Nutrition Matching

1. Nutrition Cache Tabelle
2. Default Foods Seed
3. Food Aliases Seed
4. Open Food Facts Client
5. USDA Client
6. Nutrition Calculator
7. API Ergebnisse cachen
8. Bot Antwort mit Makros

### Phase 5: Portion Intelligence

1. Portion Rules Tabelle
2. Portion Rules Seed
3. User Portion Memory Tabelle
4. Portion Engine
5. Grammwerte aus Einheiten ableiten
6. Portion Confidence berechnen
7. Tests schreiben

### Phase 6: Confidence Engine

1. Confidence Score aus Parser, Portion und Nutrition Match berechnen
2. Decision Object erzeugen
3. Schwellen implementieren:
   - `direct_save`
   - `save_as_estimate`
   - `ask_short_clarification`
   - `ask_detailed_clarification`
4. Tests schreiben

### Phase 7: Clarification Flow

1. conversation_states Tabelle
2. Inline Buttons
3. Callback Handler
4. Portion Size Flow
5. Custom Amount Flow
6. Food Match Flow
7. State Expiration
8. `/cancel`

### Phase 8: LLM Parser

1. Ollama Client
2. JSON Schema Output
3. LLM Prompt
4. Pydantic Validation
5. Timeout und Error Handling
6. Rule Parser zuerst, LLM nur als Fallback
7. Tests mit Mocked Ollama Client

### Phase 9: User Memory und Templates

1. User Portion Memory speichern
2. wiederverwenden bei ähnlichen Phrasen
3. Meal Templates speichern
4. Templates loggen
5. `/favorites`

### Phase 10: Voice

1. Telegram Voice File Download
2. Redis Job
3. Worker
4. Transcription
5. Weitergabe an Text Pipeline
6. Cleanup
7. Fehlerbehandlung

### Phase 11: Admin und Production

1. Admin Routes
2. einfache Admin Views oder JSON Endpoints
3. Error Logs
4. Audit Events
5. Sentry
6. Docker Production Setup
7. README Deployment
8. Backup Script

---

## Core Pipeline Signatur

Implementiere zentral:

```python
def handle_food_message(user_id: UUID, text: str, source: str = "text") -> BotResponse:
    ...
```

Der Ablauf muss sein:

```text
1. Preprocess
2. Check conversation state
3. Rule parse
4. If needed: LLM parse
5. Merge parsed results
6. Resolve portions
7. Match nutrition
8. Calculate macros
9. Score confidence
10. Decide action
11. Save or ask clarification
12. Return BotResponse
```

---

## Pydantic Kernschemas

Erstelle mindestens diese Schemas:

```python
class ParsedFoodItem(BaseModel):
    name: str
    quantity: float | None
    unit: str
    preparation: str | None = "unknown"
    notes: str | None = None
    confidence: float = 0.0

class ParsedFoodMessage(BaseModel):
    meal_type: str = "unknown"
    items: list[ParsedFoodItem]
    overall_confidence: float = 0.0

class ResolvedPortion(BaseModel):
    item_name: str
    grams: float | None = None
    ml: float | None = None
    confidence: float
    was_estimated: bool
    needs_clarification: bool = False
    options: list[dict] = []

class NutritionMatch(BaseModel):
    canonical_name: str
    kcal_100g: float | None
    protein_100g: float | None
    carbs_100g: float | None
    fat_100g: float | None
    source: str
    source_id: str | None = None
    confidence: float

class Decision(BaseModel):
    action: Literal[
        "direct_save",
        "save_as_estimate",
        "ask_short_clarification",
        "ask_detailed_clarification"
    ]
    confidence: float
    reason: str
```

---

## LLM Vorgaben

Das LLM darf nur strukturieren.

Es darf nicht:

- Kalorien erfinden
- Makros erfinden
- externe Fakten behaupten
- Logs speichern
- Entscheidungen über Rückfragen treffen

Prompt:

```text
Du bist ein Parser für Ernährungseinträge.
Extrahiere Lebensmittel, Mengen, Einheiten, Zubereitung und Mahlzeitentyp.
Gib ausschließlich valides JSON im vorgegebenen Schema zurück.
Berechne keine Kalorien und erfinde keine Nährwerte.
Wenn Menge oder Einheit unklar ist, setze quantity auf null und unit auf "unknown".
```

Nutze Ollama Structured Outputs mit JSON Schema, sofern verfügbar.

---

## Parser Merge Spec (Rule ↔ LLM)

Der Rule Parser läuft immer zuerst. Das LLM ist Fallback und Ergänzung, niemals Primärquelle. Diese Spec ist verbindlich, wenn beide Parser laufen.

### Wann das LLM aufgerufen wird

Das LLM wird aufgerufen, wenn **mindestens eine** Bedingung zutrifft:

- `rule_result.overall_confidence < 0.6`
- `rule_result.items` ist leer
- ungenutzte Text-Spans > 8 Zeichen sind übrig (ohne Stoppwörter wie "und", "mit", "ein", "einen", "eine")
- Mahlzeitkontext-Verben im Text ("hatte", "gegessen", "gefrühstückt", "gabs") UND `rule_confidence < 0.85`

Sonst: LLM überspringen, Rule-Result direkt verwenden. Diese Entscheidung als Audit-Event `llm_skipped` loggen (für Cost-Monitoring).

### Merge-Algorithmus

Eingaben: `rule: ParsedFoodMessage`, `llm: ParsedFoodMessage`
Ausgabe: `merged: ParsedFoodMessage`

1. **Normalisieren**: Alle Item-Namen aus beiden Parsern via `food_aliases` zu `canonical_name` mappen.
2. **Halluzinationsschutz** (nur LLM-Items): Jedes LLM-Item muss als Token im Originaltext vorkommen — case-insensitive Substring-Match ODER Levenshtein-Distanz ≤ 2 zu einem Token. Wenn nein: Item verwerfen und Audit-Event `llm_hallucination_blocked` schreiben mit `{item_name, original_text}`.
3. **Item-Liste mergen** nach `canonical_name`:
   - nur in Rule → übernehmen
   - nur in LLM (nach Schritt 2 überlebt) → übernehmen
   - in beiden → Item-Merge (siehe unten)
4. **`meal_type`**: LLM gewinnt, falls `llm.meal_type != "unknown"`. Sonst Rule.
5. **`overall_confidence`** = `mean(merged.items[*].confidence)`, minus 0.05 wenn ≥ 1 Merge-Konflikt aufgetreten ist.

### Item-Merge bei gleichem `canonical_name`

**Quantity/Unit (Reihenfolge ist die Priorität):**
1. Rule hat explizite Gewichts-/Volumenangabe (Regex `\d+(\.\d+)?\s*(g|kg|ml|l)`) → Rule gewinnt komplett.
2. Rule `quantity=null`, LLM hat Zahl → LLM gewinnt.
3. Beide haben gleiche Stück-/Slice-/Portion-Werte → Rule gewinnt (deterministischer).
4. Unterschiedliche `unit` → Rule gewinnt (nur Rule normalisiert Einheiten deterministisch).
5. Beide `quantity=null` → behalte LLM (mehr Kontext) und markiere `needs_clarification=true`.

**Multi-Word-Foods**: Wenn Rule eine Phrase in 2+ Items splittet und LLM sie als 1 Item führt (z. B. "Whey Protein", "Chicken Bowl"), prüfe Treffer in `food_aliases`. Treffer → LLM-Variante (1 Item) gewinnt. Kein Treffer → Rule gewinnt.

**Notes**: Unique values mit `; ` konkatenieren.
**Preparation**: Spezifischeres gewinnt (`cooked` / `grilled` / `fried` / `raw` > `unknown`).
**Confidence**: `merged.confidence = max(rule.confidence, llm.confidence) - 0.05`.

### Audit-Pflicht

Bei jedem nicht-trivialen Merge (Konflikt in Quantity, Unit, Item-Identität): `audit_events` mit `event_type="parser_merge_conflict"` und Payload `{rule_item, llm_item, decision, reason}`. Pflicht für Eval-Auswertung.

---

## Open Food Facts Vorgaben

- Verwende einen eigenen User-Agent aus `.env`
- Implementiere Rate Limiting
- Cache Ergebnisse in `nutrition_items`
- Behandle leere Ergebnisse sauber
- Nutze Open Food Facts bevorzugt für Markenprodukte und Barcodes

---

## USDA Vorgaben

- API Key über `.env`
- Implementiere Rate Limiting
- Nutze USDA bevorzugt für generische Lebensmittel
- Cache Ergebnisse
- Behandle cooked/raw möglichst sauber

---

## Telegram UX Vorgaben

Antworten sollen kurz, klar und freundlich sein.

Erfolgreicher Log:

```text
Gespeichert ✅

250g Skyr
1 Banane, geschätzt 120g
30g Whey

Gesamt:
438 kcal
52g Protein
42g Carbs
4g Fett

Heute:
1.240 / 2.400 kcal
112 / 180g Protein
```

Clarification:

```text
Welche Portion passt am besten?

[ Klein ] [ Normal ] [ Groß ] [ Eigene Menge ]
```

Regeln:

- nie mehr als eine Frage gleichzeitig
- bei Unsicherheit transparent sein
- Schätzungen markieren
- User kann korrigieren
- User kann abbrechen

---

## Tests

Schreibe Tests, bevor du komplexere Module erweiterst.

Mindesttests:

```text
test_text_numbers.py
test_units.py
test_rule_parser.py
test_portion_engine.py
test_confidence_engine.py
test_nutrition_calculator.py
test_clarification_service.py
```

Mindestens diese Eingaben testen:

```text
250g Skyr, 1 Banane und 30g Whey
zwei Eier und eine Scheibe Brot
ein Teller Pasta
eine Bowl mit Hähnchen
eine Schüssel Haferflocken
500ml Milch
1 Döner
Dönerbox mit Pommes
Chicken Bowl mit Reis
ein Kaffee mit Milch
```

---

## Goldstandard Test-Outputs

Erwartete Outputs für die 10 Mindesttest-Eingaben oben. Sollwerte für Regression-Tests von Rule Parser, Portion Engine und Confidence Engine — keine Implementation-Vorgabe. Confidence-Werte sind approximativ (±0.10 ist ok).

**Default-Portionen (aus Portion Rules Seed):**
Banane=120g · Ei=60g · Scheibe Brot=45g · Scheibe Toast=25g · Glas Milch=250ml · Bowl Haferflocken=80g · Pasta-Teller {S=250g, M=350g, L=500g} · Reis gekocht Portion=180g · Döner=650 kcal · Dönerbox+Pommes=850 kcal · Chicken Bowl Reis=700 kcal · Chicken Bowl Salat=450 kcal.

### 1. "250g Skyr, 1 Banane und 30g Whey"

```json
{
  "items": [
    {"name": "Skyr",   "quantity": 250, "unit": "g",     "grams": 250, "was_estimated": false, "confidence": 0.95},
    {"name": "Banane", "quantity": 1,   "unit": "piece", "grams": 120, "was_estimated": true,  "confidence": 0.90},
    {"name": "Whey",   "quantity": 30,  "unit": "g",     "grams": 30,  "was_estimated": false, "confidence": 0.95}
  ],
  "llm_called": false,
  "decision": "direct_save",
  "overall_confidence": 0.93
}
```

### 2. "zwei Eier und eine Scheibe Brot"

```json
{
  "items": [
    {"name": "Ei",   "quantity": 2, "unit": "piece", "grams": 120, "was_estimated": true, "confidence": 0.90},
    {"name": "Brot", "quantity": 1, "unit": "slice", "grams": 45,  "was_estimated": true, "confidence": 0.85}
  ],
  "llm_called": false,
  "decision": "direct_save",
  "overall_confidence": 0.88
}
```

### 3. "ein Teller Pasta"

```json
{
  "items": [
    {"name": "Pasta", "quantity": 1, "unit": "plate", "grams": null,
     "needs_clarification": true,
     "options": [
       {"label": "Klein",        "grams": 250},
       {"label": "Normal",       "grams": 350},
       {"label": "Groß",         "grams": 500},
       {"label": "Eigene Menge", "type":  "custom"}
     ],
     "confidence": 0.50}
  ],
  "llm_called": false,
  "decision": "ask_short_clarification",
  "clarification_type": "portion_size",
  "overall_confidence": 0.50
}
```

### 4. "eine Bowl mit Hähnchen"

```json
{
  "items": [
    {"name": "Bowl", "quantity": 1, "unit": "bowl", "notes": "mit Hähnchen",
     "needs_clarification": true,
     "options": [
       {"label": "Reis + Hähnchen",  "default_kcal": 700},
       {"label": "Salat + Hähnchen", "default_kcal": 450},
       {"label": "Poke / Fisch",     "default_kcal": 600},
       {"label": "Andere",           "type": "custom"}
     ],
     "confidence": 0.40}
  ],
  "llm_called": true,
  "decision": "ask_detailed_clarification",
  "clarification_type": "meal_variant",
  "overall_confidence": 0.40
}
```

### 5. "eine Schüssel Haferflocken"

Erstaufruf (kein User-Memory-Treffer):

```json
{
  "items": [
    {"name": "Haferflocken", "quantity": 1, "unit": "bowl", "grams": 80, "was_estimated": true, "confidence": 0.70}
  ],
  "llm_called": false,
  "decision": "save_as_estimate",
  "post_save_action": "ask_save_to_memory",
  "overall_confidence": 0.70
}
```

Nach erfolgtem User-Memory-Eintrag (`schüssel haferflocken → 80g` für diesen User):

```json
{"decision": "direct_save", "overall_confidence": 0.92, "memory_hit": true}
```

### 6. "500ml Milch"

```json
{
  "items": [
    {"name": "Milch", "quantity": 500, "unit": "ml", "ml": 500, "grams": 515, "was_estimated": false, "confidence": 0.95}
  ],
  "llm_called": false,
  "decision": "direct_save",
  "overall_confidence": 0.95
}
```

Note: `grams = ml × 1.03` für Milchdichte. Rule Parser kann auch `grams=500` zurückgeben — beides ok.

### 7. "1 Döner"

```json
{
  "items": [
    {"name": "Döner", "quantity": 1, "unit": "piece", "grams": null, "default_kcal": 650, "was_estimated": true, "confidence": 0.70}
  ],
  "llm_called": false,
  "decision": "save_as_estimate",
  "overall_confidence": 0.70
}
```

### 8. "Dönerbox mit Pommes"

```json
{
  "items": [
    {"name": "Dönerbox Pommes", "quantity": 1, "unit": "piece", "grams": null, "default_kcal": 850, "was_estimated": true, "confidence": 0.70}
  ],
  "llm_called": false,
  "decision": "save_as_estimate",
  "overall_confidence": 0.70
}
```

### 9. "Chicken Bowl mit Reis"

```json
{
  "items": [
    {"name": "Chicken Bowl Reis", "quantity": 1, "unit": "portion", "grams": null, "default_kcal": 700, "was_estimated": true, "confidence": 0.75}
  ],
  "llm_called": false,
  "decision": "save_as_estimate",
  "overall_confidence": 0.75
}
```

### 10. "ein Kaffee mit Milch"

```json
{
  "items": [
    {"name": "Kaffee", "quantity": 1, "unit": "cup", "grams": null, "default_kcal": 5, "was_estimated": true, "confidence": 0.90},
    {"name": "Milch",  "quantity": null, "unit": "unknown", "notes": "in Kaffee",
     "needs_clarification": true,
     "options": [
       {"label": "Schuss (10ml)",       "ml": 10},
       {"label": "Etwas (30ml)",        "ml": 30},
       {"label": "Halbes Glas (125ml)", "ml": 125},
       {"label": "Eigene Menge",        "type": "custom"}
     ],
     "confidence": 0.40}
  ],
  "llm_called": true,
  "decision": "ask_short_clarification",
  "clarification_type": "custom_amount",
  "overall_confidence": 0.55
}
```

### Hinweise zur Verwendung

- Diese Outputs als pytest-Fixtures in `tests/fixtures/goldstandard.json` ablegen.
- Vergleiche pro Item: `name` (canonical), `unit`, `grams` (±10 %), `was_estimated`, `confidence` (±0.10).
- `decision.action` muss exakt matchen — sonst Regression.
- `llm_called` als Cost-Smoke-Test: Eingaben 1, 2, 3, 5, 6, 7, 8, 9 dürfen das LLM **nicht** aufrufen.

---

## Akzeptanzkriterien erste lauffähige Version

Die erste nutzbare Version ist fertig, wenn:

1. User kann per Telegram Textnachricht eine einfache Mahlzeit loggen
2. Bot berechnet Kalorien und Makros
3. Bot speichert Log in PostgreSQL
4. `/today` zeigt Tagesstand
5. unklare Portionen erzeugen Telegram Buttons
6. Button-Antwort speichert finalen Log
7. User Portion Memory funktioniert für mindestens einen Flow
8. Open Food Facts und USDA sind angebunden
9. Nutrition Cache funktioniert
10. Rule Parser wird vor LLM verwendet
11. LLM Parser kann strukturierte JSON Outputs liefern
12. Tests für Core Logic laufen
13. Docker Compose startet App, DB und Redis
14. Secrets liegen nicht im Code
15. README erklärt Setup und Start

---

## Nicht bauen in erster Version

Baue nicht:

- Mobile App
- Payment
- Barcode Scanner
- Foto-Erkennung
- Wearable Integration
- komplexe Analytics
- Coach Dashboard
- automatische Ernährungspläne

Diese Dinge sind spätere Phasen.

---

## Qualitätsregeln

- Schreibe sauberen, modularen Code
- Keine Business-Logik direkt in Telegram Handlern
- Telegram Handler sollen nur Input an Services weitergeben
- Pydantic für Datenvalidierung nutzen
- Datenbankzugriffe über Repository Layer kapseln
- Keine hardcoded API Keys
- Gute Fehlerbehandlung
- Logging für wichtige Entscheidungen
- Tests für alle Kernentscheidungen
- Seed-Daten reproduzierbar machen
- Externe APIs immer mit Timeout aufrufen
- LLM Calls immer mit Timeout und Fallback

---

## Wichtigste Designentscheidung

Wenn du unsicher bist, priorisiere immer diese Reihenfolge:

```text
1. korrekte Produktlogik
2. klare Nutzerführung
3. testbare Architektur
4. günstiger Betrieb
5. spätere Skalierbarkeit
```

Nicht versuchen, alles über das LLM zu lösen.

Die Nutrition Intelligence Engine ist wichtiger als das Modell.

---

## Finaler Auftrag

Implementiere das Projekt schrittweise entsprechend `todo.md`.

Beginne mit Sprint 1 und baue dann Sprint für Sprint weiter. Nach jedem Sprint soll der Code lauffähig und testbar sein.

Dokumentiere im README:

- Setup
- Environment Variables
- Docker Start
- Telegram Bot Setup
- Ollama Setup
- USDA/Open Food Facts Setup
- Tests
- Deployment Hinweise
