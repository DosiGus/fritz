# Office Hours Baseline: Fritz Telegram Nutrition Tracker

Date: 2026-04-29
Mode: Builder / product diagnostic
Scope: Whole project baseline, not a diff review

## One-Line Read

Fritz is a strong product idea with a surprisingly complete backend skeleton: Telegram UX, food pipeline, portion intelligence, confidence decisions, clarification state, user memory, templates, admin/audit, voice worker, Docker, migrations, and tests are all present. The product risk is now concentrated in one place: making the food-understanding core reliable enough that users trust it more than they hate tracking food.

## Product Thesis

The best version of this product is not "AI calorie tracker". That framing is too broad and too easy to disappoint.

The sharper thesis is:

> The fastest way to log food approximately well enough, without opening a tracking app.

This is the right promise. It accepts that food tracking is approximate, then competes on speed, memory, and low-friction correction. The product wins if the user feels: "I can send one message and move on."

## Current Product Shape

The repo already supports the core loop:

1. User sends a text or voice Telegram message.
2. The app normalizes input.
3. A food intent parser turns language into structured food items.
4. Portion resolution converts quantities into grams, ml, or clarification options.
5. Nutrition matching finds cached, default, Open Food Facts, or USDA values.
6. Confidence decides direct save, save as estimate, or ask a question.
7. Conversation state handles clarification, custom amounts, nutrition retry, edits, templates, and memory.
8. Logs, audit events, and admin endpoints provide operational visibility.

That is a real product architecture, not a toy bot.

## What Is Strong

- The product promise is coherent: Telegram is a good first UI because it removes app friction.
- The pipeline is modular in the right places: parsing, portions, matching, confidence, clarification, memory.
- Conversation state is a real advantage. It lets Fritz ask one question at a time instead of dumping forms onto the user.
- User memory is strategically important. Personal portion habits are where this can become better than generic trackers.
- Meal templates/favorites fit the "do not make me repeat myself" product promise.
- Audit events and admin endpoints exist early, which is unusual and good for beta operations.
- Tests are broad for this stage: 169 collected tests across admin, health, voice, units, confidence, portions, nutrition, and core flows.
- Production Compose exists with migration gating and health checks.

## Main Product Risk

The current product promise depends on graceful degradation. If the parser or nutrition source is unavailable, the bot should still be useful for common inputs.

Right now the architecture is drifting toward "LLM-first or fail". That is risky because the user's most common messages are simple:

- `250g Skyr`
- `1 Banane`
- `2 Eier`
- `30g Whey`
- `500ml Milch`

Those should never require a live LLM call. They are the wedge. If those fail because an API key, DNS, timeout, or model response fails, the product feels unreliable immediately.

## Architectural Assessment

The architecture wants a layered parser:

1. Hard facts and deterministic parser for obvious inputs.
2. LLM intent parser for ambiguous/composite language.
3. Validator that prevents LLM output from overwriting hard facts.
4. Fallback behavior that can still log simple meals or ask a useful question.

The repo currently has hard facts and an OpenAI structured parser, but the old rule/local parser layer is being removed. That can be a good simplification only if deterministic parsing remains for the common path. Without it, the system becomes easier to reason about but worse for the user.

The confidence engine is directionally right. The next quality jump is calibration: confidence should reflect user-visible risk, not just internal component scores.

## Data Model Assessment

The database shape is solid for a beta:

- Users and goals
- Food logs and log items
- Nutrition cache and aliases
- Portion rules and personal memory
- Meal templates
- Conversation states
- Audit events and API request logs

Potential issues to watch:

- `conversation_states` appears to allow multiple active states per user unless repository methods enforce deletion consistently.
- Nutrition aliases and cache matching will need stronger uniqueness rules as real usage grows.
- Audit events are useful now, but metrics will become slow/noisy without retention or indexed query patterns.
- User memory needs guardrails so one bad correction does not poison future logs.

## UX Assessment

The UX principle is good: one message in, one clear response out, one question max when needed.

The saved-log actions are also right:

- Passt
- Korrigieren
- Als Favorit speichern
- Löschen

This creates a feedback loop. The missing UX layer is trust language. The bot should make uncertainty visible without sounding broken. Users can forgive estimates; they do not forgive silent wrongness or generic failure messages.

Bad failure:

> Ich konnte deinen Eintrag gerade nicht verarbeiten.

Better failure:

> Ich erkenne die Menge, aber nicht das Lebensmittel sicher. Meinst du Skyr, Joghurt oder Magerquark?

## Test And Quality Assessment

The test suite is already valuable. It caught the main architecture issue immediately:

Command run:

```bash
.venv/bin/pytest
```

Result:

```text
160 passed, 9 failed
```

The failing tests are concentrated in Sprint 3 core flows and share one failure shape: the new food intent parser returns no parsed message when the OpenAI call fails, so downstream flows get no decision or saved log.

That is not just a test problem. It reflects a product reliability problem.

## Deployment Assessment

The deployment story is close to beta-ready for a small VPS:

- FastAPI app
- Telegram bot service
- Worker service
- Postgres
- Redis
- Production Compose overlay
- Migration service before app/bot/worker startup
- `/ready` checks database and Redis
- Optional Sentry
- Admin token gating

Before beta, the operational gap is not infrastructure. It is deterministic behavior under partial failure: OpenAI unavailable, Telegram send failure, Open Food Facts timeout, USDA missing, Redis down, duplicate callback, expired state.

## Narrowest Useful Beta

Do not try to make every meal work first.

The best beta wedge is:

1. Gym/fitness users logging repeatable meals in German.
2. Strong support for structured simple entries.
3. Good support for common ambiguous portions.
4. Fast correction and memory.
5. Honest estimates for restaurant-style meals.

Target examples:

- `250g Skyr, 1 Banane, 30g Whey`
- `2 Eier mit Toast`
- `eine Schüssel Haferflocken`
- `ein Döner`
- `ein Teller Pasta`
- `Cappuccino mit Milch`

If these feel good, the product has a real wedge.

## What I Would Do Next

1. Restore or replace deterministic parsing for simple inputs.
   Simple gram/ml/piece inputs should not depend on OpenAI.

2. Keep the OpenAI food intent parser for complex language.
   Use it where it adds value: composite meals, modifiers, meal type, natural speech.

3. Define parser fallback policy explicitly.
   For example: hard facts parser succeeds -> continue; OpenAI succeeds -> enrich; OpenAI fails -> use deterministic parse or ask one useful question.

4. Turn the current failing Sprint 3 tests into the core acceptance suite.
   These tests represent user-visible workflows, not implementation details.

5. Add a beta "golden foods" set.
   A fixed list of 30 to 50 common German fitness foods should work offline and deterministically.

6. Tune response copy for trust.
   The product should say when it estimated, when it needs help, and what the user can do next.

7. Use admin metrics to drive beta iteration.
   Track parser unavailable, nutrition retry, clarification asked/resolved, delete/edit rate, and memory accepted rate.

## Key Decision

The big product decision is not "OpenAI vs rules". It is:

> Should Fritz optimize for maximum language intelligence, or maximum logging reliability?

For this product, reliability wins first. Intelligence is a layer on top. A food tracker that logs simple meals every time is useful. A clever bot that sometimes cannot log `100g Skyr` is not.

## Recommended Next gstack Step

Run `/plan-eng-review` next on this baseline question:

> How should the parser architecture be structured so simple food logs are deterministic, complex food logs use OpenAI, and tests never require network access?

After that, run `/review` on the current diff.

## Status

DONE_WITH_CONCERNS

Concerns:

- The current parser direction risks making the most common user path depend on a network LLM call.
- The test suite is correctly warning that core user flows are not stable.
- The repo is close enough to beta that reliability work now matters more than adding breadth.
