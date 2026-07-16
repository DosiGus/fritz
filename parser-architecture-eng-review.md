# Plan Eng Review: Parser Architecture

Date: 2026-04-29
Question: How should the parser architecture be structured so simple food logs are deterministic, complex food logs use OpenAI, and tests never require network access?
Input: `office-hours-project-baseline.md`
Status: DONE_WITH_CONCERNS

## Recommendation

Use a layered parser pipeline:

```text
Telegram text / voice transcript
  |
  v
normalize_text()
  |
  v
extract_hard_facts()
  |
  v
deterministic parser
  |        \
  |         \ no confident parse
  |          v
  |       OpenAI food intent parser
  |          |
  |          v
  |       adapter + hard-fact validator
  |          |
  v          v
ParsedFoodMessage
  |
  v
portion_engine -> nutrition_matcher -> confidence_engine
  |
  v
save / estimate / clarify / nutrition retry
```

OpenAI should enrich or resolve complex language. It should not be required for obvious logs like `100g Skyr`, `1 Banane`, `2 Eier`, `500ml Milch`, or `30g Whey`.

The right implementation is a small deterministic parser plus a routing policy, not a resurrected full rule-parser stack.

## Step 0: Scope Challenge

### What Already Exists

- `app/services/food_pipeline.py` already owns the user-facing flow from message to saved log.
- `app/services/hard_fact_extractor.py` already extracts quantities, explicit gram/ml amounts, meal type, portion sizes, and separate markers.
- `app/services/food_intent_adapter.py` already converts a `FoodIntent` into `ParsedFoodMessage`.
- `app/services/food_intent_validator.py` already protects downstream flow from bad LLM structure by filtering components and preserving context.
- `app/services/portion_engine.py` already handles explicit gram/ml conversion, personal memory, portion rules, LLM-provided options, and generic clarification.
- `app/services/nutrition_matcher.py` already does cache, aliases, fuzzy cache, static defaults, Open Food Facts, and USDA.
- `tests/test_sprint3_core_flows.py` already expresses the product-level acceptance suite that should stay green.
- `tests/test_food_intent_v2.py` already verifies structured OpenAI calls and patched complex flows.

### Minimum Change Set

Implement one new deterministic parse layer and one routing policy:

1. Add a deterministic parser that returns `ParsedFoodMessage | None`.
2. Update `parse_with_food_intent_v2()` to try deterministic parsing before OpenAI for simple inputs.
3. If deterministic parsing is not enough, call OpenAI.
4. If OpenAI fails, fall back to deterministic parse if any safe parse exists.
5. In tests, force `OPENAI_API_KEY` off by default and mock OpenAI only in tests that explicitly test OpenAI.

This should touch about 4 to 6 files:

- `app/services/food_intent_pipeline.py`
- new or restored `app/services/deterministic_food_parser.py`
- `tests/conftest.py`
- `tests/test_food_intent_v2.py`
- `tests/test_sprint3_core_flows.py`
- maybe `app/services/static_data.py` for aliases or golden foods

Complexity check: this is under the 8-file smell threshold and introduces one new service. Good.

### Defer These

- Full recipe decomposition.
- Full natural language grammar.
- LLM eval harness.
- New data model.
- Async OpenAI client migration.
- Admin UI changes.
- Rebuilding the deleted old parser stack wholesale.

## Architecture Review

### 1. Current Pipeline Is LLM-First Or Fail

`app/services/food_intent_pipeline.py:20-24` says the parser is LLM-first and returns `None` when the OpenAI call fails. `app/services/food_pipeline.py:56-64` turns that into a generic failure response.

Severity: P1
Confidence: 10/10

This breaks the product promise. A user sending `100g Skyr` should not depend on DNS, API key config, model availability, or OpenAI latency.

Decision:

- 1A. Recommended: deterministic-first routing for simple inputs, OpenAI for complex inputs.
- 1B. Acceptable shortcut: OpenAI-first, deterministic fallback only on OpenAI failure.
- 1C. Not recommended: keep LLM-first and mock tests only.

Pick 1A. It matches explicit-over-clever and keeps the smallest reliable core.

### 2. Hard Facts Exist But Are Not Sufficiently Used

`app/services/hard_fact_extractor.py:23-30` already extracts the facts needed for a safe deterministic parser. Today those facts are passed into OpenAI prompting and adapter validation, but they do not produce a parse by themselves.

Severity: P2
Confidence: 9/10

The missing layer is not another big parser. It is a small mapper from hard facts plus leftover food text to `ParsedFoodItem`.

Decision:

- 2A. Recommended: create `deterministic_food_parser.py` that handles explicit amount-item pairs and simple quantity-item pairs.
- 2B. Put this directly in `food_intent_pipeline.py`.
- 2C. Restore the old deleted `rule_parser.py` wholesale.

Pick 2A. It is more testable than inline code and much smaller than restoring old complexity.

### 3. OpenAI Should Be A Boundary, Not A Global Dependency

`app/services/openai_food_intent_parser.py:146-176` correctly returns `None` on missing key or HTTP/parser errors. The problem is that upstream treats `None` as total parser failure instead of one unavailable parse strategy.

Severity: P1
Confidence: 9/10

The parser pipeline should treat OpenAI as one strategy among several. That makes failure visible in audit logs but not catastrophic for simple user logs.

Decision:

- 3A. Recommended: keep `parse_food_intent()` as-is and change orchestration in `food_intent_pipeline.py`.
- 3B. Add fallback logic inside `openai_food_intent_parser.py`.
- 3C. Raise exceptions and handle them in `food_pipeline.py`.

Pick 3A. Strategy orchestration belongs in the pipeline, not inside the OpenAI client.

### Architecture Diagram

```text
parse_with_food_intent_v2(text)
  |
  +-- facts = extract_hard_facts(text)
  |
  +-- simple = parse_deterministic(text, facts)
  |     |
  |     +-- confident simple parse? ---- yes ---> validate_deterministic(simple)
  |     |                                      |
  |     |                                      v
  |     |                                ParsedFoodMessage
  |     |
  |     +-- no
  |
  +-- intent = parse_food_intent(text, facts)
        |
        +-- success ---> food_intent_to_parsed()
        |                 |
        |                 v
        |              validate_food_intent()
        |                 |
        |                 v
        |              ParsedFoodMessage
        |
        +-- failure ---> simple fallback exists?
                          |
                          +-- yes -> ParsedFoodMessage
                          +-- no  -> None
```

## Code Quality Review

### 1. Avoid Rebuilding A Parallel Pipeline

The deterministic parser must only produce `ParsedFoodMessage`. It must not resolve portions, match nutrition, calculate calories, or decide confidence. Those already exist downstream.

Severity: P2
Confidence: 8/10

If the deterministic parser starts calculating grams or nutrition, the codebase gets two food pipelines. That creates bugs where simple and complex inputs behave differently.

Decision:

- 1A. Recommended: deterministic parser outputs only `ParsedFoodMessage`.
- 1B. Let deterministic parser also resolve obvious grams.
- 1C. Let deterministic parser produce full `BotResponse`.

Pick 1A. It keeps the system DRY and preserves one downstream behavior path.

### 2. Canonicalization Needs A Tiny Alias Layer

`app/services/static_data.py:111-113` currently returns the name unchanged because the LLM is expected to produce canonical names. A deterministic parser will see raw user words like `whey`, `eier`, `bananen`, and maybe lowercase names.

Severity: P2
Confidence: 8/10

Without a small alias/canonicalization step, deterministic parsing will produce items that miss static nutrition and portion rules.

Decision:

- 2A. Recommended: add a small parser-local alias map for golden foods, then let DB aliases remain the production source.
- 2B. Expand global `canonicalize()` heavily.
- 2C. Require users to type canonical names.

Pick 2A. It keeps beta reliability high without pretending static code is the final nutrition database.

### 3. Test Defaults Should Disable Network By Construction

`tests/conftest.py:5-7` sets database, Telegram, and USDA defaults but does not force `OPENAI_API_KEY` empty. If a developer has `OPENAI_API_KEY` in their shell or `.env`, tests can accidentally hit the network.

Severity: P1
Confidence: 9/10

The test suite should not need developer discipline to avoid network. Tests that cover OpenAI should patch `httpx.post` and `settings.openai_api_key` explicitly.

Decision:

- 3A. Recommended: set `OPENAI_API_KEY=""` in `tests/conftest.py`, then patch it only in OpenAI-specific tests.
- 3B. Add a pytest marker for network tests.
- 3C. Rely on mocks in individual tests.

Pick 3A now. Add marker later only if real network evals are introduced.

## Test Review

Detected framework: Python + pytest from `nutrition-tracker/pytest.ini` and `tests/`.

Current baseline:

```text
.venv/bin/pytest
160 passed, 9 failed
```

The 9 failures are regressions in `tests/test_sprint3_core_flows.py`. They are not merely stale tests; they cover user-visible flows that should remain valid.

### Coverage Diagram

```text
CODE PATHS                                                     USER FLOWS
[+] app/services/food_intent_pipeline.py                       [+] Simple text logging
  ├── [GAP] deterministic parse before OpenAI                     ├── [GAP] [CRITICAL] 100g Skyr saves without OpenAI
  ├── [GAP] OpenAI skipped for explicit amount food                ├── [GAP] 1 Banane saves or estimates without OpenAI
  ├── [★★ TESTED] OpenAI structured response is parsed             ├── [GAP] 250g Skyr, 1 Banane multi-item save
  ├── [GAP] OpenAI failure falls back to deterministic parse       └── [GAP] no OPENAI_API_KEY still useful for simple logs
  └── [★★ TESTED] OpenAI unavailable returns friendly error

[+] new app/services/deterministic_food_parser.py               [+] Complex language logging
  ├── [GAP] amount-item: 100g Skyr                                 ├── [★★ TESTED] patched Cappuccino OpenAI flow
  ├── [GAP] quantity-item: 1 Banane / 2 Eier                       ├── [★★ TESTED] patched Falafel composite flow
  ├── [GAP] mixed list: 250g Skyr, 1 Banane, 30g Whey              └── [GAP] [→EVAL later] real prompt quality corpus
  ├── [GAP] meal type preserved from hard facts
  ├── [GAP] parser refuses complex composite input
  └── [GAP] no false parse for template naming state

[+] app/services/food_pipeline.py                               [+] Correction/template/memory flows
  ├── [★★★ TESTED] save/edit/delete/template paths exist           ├── [GAP] edit_last still works without OpenAI
  ├── [GAP] simple parser success continues downstream             ├── [GAP] template save after deterministic parse
  └── [GAP] parser unavailable only when no strategy can parse      └── [GAP] memory prompt from deterministic portion estimate

COVERAGE: 5/22 paths tested directly (23%)
QUALITY: ★★★:1 ★★:4 ★:0
GAPS: 17, including 1 critical regression cluster and 1 future eval gap
```

### Required Tests

Add or update these tests:

1. `tests/test_deterministic_food_parser.py`
   - `100g Skyr` -> one `ParsedFoodItem(name="Skyr", quantity=100, unit="g")`
   - `1 Banane` -> one `ParsedFoodItem(name="Banane", quantity=1, unit="piece")`
   - `2 Eier` -> canonical singular/plural handling
   - `250g Skyr, 1 Banane, 30g Whey` -> three items
   - `zum Frühstück 250g Skyr` -> meal type preserved
   - `Falafel-Sandwich mit Hummus und Halloumi` -> returns `None` so OpenAI handles it

2. `tests/test_food_intent_v2.py`
   - deterministic parser is used when OpenAI key is missing
   - OpenAI is not called for deterministic simple input
   - OpenAI failure falls back to deterministic parse when possible
   - OpenAI failure still returns friendly error when deterministic parser cannot safely parse

3. `tests/test_sprint3_core_flows.py`
   - keep the existing failing tests and make them pass
   - add explicit patch proving no `httpx.post` occurs during simple local flows

4. `tests/conftest.py`
   - set `OPENAI_API_KEY=""`

Regression rule: the Sprint 3 failures are critical regression tests. Do not delete or weaken them.

## Performance Review

### 1. Deterministic-First Reduces Latency And Cost

OpenAI-first adds network latency and cost to the highest-volume path. Deterministic-first makes common logs local and fast.

Severity: P2
Confidence: 9/10

Decision:

- 1A. Recommended: deterministic-first for obvious simple logs.
- 1B. OpenAI-first with deterministic fallback.

Pick 1A. It improves both reliability and performance.

### 2. Avoid Broad DB Lookups In The Parser Layer

The deterministic parser should not query nutrition tables to decide whether a token is a food. `nutrition_matcher.py` already contains DB matching and external API fallback.

Severity: P2
Confidence: 8/10

Decision:

- 2A. Recommended: parser uses small lexical rules and aliases only; nutrition verification stays downstream.
- 2B. Parser queries DB aliases/cache to decide parse confidence.

Pick 2A. It keeps parser latency stable and avoids coupling parsing to nutrition storage.

## Failure Modes

| Codepath | Production failure | Test? | Handling? | User sees |
|---|---|---:|---:|---|
| deterministic amount parser | bad regex parses `100g` but loses food name | planned | planned | either saved correctly or useful fallback |
| deterministic list parser | commas/`und` split wrong | planned | partial | should ask or use OpenAI |
| OpenAI parser | timeout/DNS/API error | partial today | yes, but too blunt | should still log simple input |
| OpenAI parser | invalid JSON/schema mismatch | partial today | yes | simple fallback or friendly retry |
| nutrition matcher | Open Food Facts timeout | existing pattern | partial | nutrition retry if no match |
| confidence engine | low confidence simple item | existing | yes | clarification |
| template naming state | parser eats template name as food | existing path | yes | saves template name |

Critical gap: OpenAI failure for simple food logs has no useful fallback today.

## NOT In Scope

- No new database tables.
- No admin dashboard UI changes.
- No full recipe decomposition.
- No production LLM eval harness in this PR.
- No async OpenAI/httpx refactor.
- No rewrite of nutrition matching.
- No resurrecting the entire deleted rule parser stack.

## Worktree Parallelization

Sequential implementation is recommended. The main changes all touch `app/services/` parser orchestration and `tests/`, so parallel worktrees would create more merge friction than speed.

Dependency table:

| Step | Modules touched | Depends on |
|---|---|---|
| deterministic parser | `app/services/`, `tests/` | — |
| parser orchestration | `app/services/`, `tests/` | deterministic parser |
| test hardening | `tests/` | parser orchestration |
| static aliases/golden foods | `app/services/`, `tests/` | deterministic parser |

Execution order: deterministic parser -> orchestration -> test hardening -> final full pytest.

## Implementation Plan

1. Add `app/services/deterministic_food_parser.py`.
2. Keep output shape limited to `ParsedFoodMessage`.
3. Support only high-confidence beta wedge grammar:
   - explicit amount + food
   - quantity + known unitless food
   - comma/`und` separated simple lists
   - meal type from hard facts
4. Add small canonical alias map:
   - `whey` -> `Whey Protein`
   - `eier`/`ei` -> `Ei`
   - `bananen`/`banane` -> `Banane`
   - `skyr` -> `Skyr`
   - `haferflocken` -> `Haferflocken`
5. Update `parse_with_food_intent_v2()`:
   - collect hard facts
   - attempt deterministic parse
   - if deterministic parse is high-confidence simple, return it
   - otherwise call OpenAI
   - if OpenAI fails and deterministic parse exists, return deterministic parse
   - if both fail, return `None`
6. Harden test environment:
   - force `OPENAI_API_KEY=""` in `tests/conftest.py`
   - patch OpenAI only inside OpenAI tests
7. Run:
   - `.venv/bin/pytest tests/test_deterministic_food_parser.py`
   - `.venv/bin/pytest tests/test_food_intent_v2.py tests/test_sprint3_core_flows.py`
   - `.venv/bin/pytest`

## Suggested Inline Diagram Comments

Add a small ASCII pipeline diagram to `app/services/food_intent_pipeline.py`, not every file. That is the orchestration point. Do not add diagrams inside the deterministic parser unless the parsing branches become hard to follow.

## TODO Candidates

Do not add these yet unless we decide to expand scope:

1. LLM eval corpus for 30-50 representative German meal utterances.
2. Admin metric for deterministic vs OpenAI parse rate.
3. DB-backed alias seed expansion for beta foods.
4. Network-blocking pytest fixture that fails any unmocked external HTTP call.

## Completion Summary

- Step 0: Scope Challenge — scope reduced to deterministic parser plus orchestration.
- Architecture Review: 3 issues found.
- Code Quality Review: 3 issues found.
- Test Review: diagram produced, 17 gaps identified.
- Performance Review: 2 issues found.
- NOT in scope: written.
- What already exists: written.
- TODOS.md updates: 4 candidates identified, not applied.
- Failure modes: 1 critical gap flagged.
- Outside voice: skipped.
- Parallelization: sequential implementation, no useful parallel lanes.
- Lake Score: complete local parser reliability chosen over shortcut test mocking.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | Not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | Not run |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | DONE_WITH_CONCERNS | 8 issues, 1 critical gap |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | Backend-only plan |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | Not run |

VERDICT: ENG PLAN REVIEW COMPLETE — ready to implement after accepting deterministic-first parser architecture.
