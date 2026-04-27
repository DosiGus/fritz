# Vision: Telegram Nutrition Tracker

## 1. Produktidee

Wir bauen einen ready-to-use Nutrition Tracker, der über Telegram bedient wird. Nutzer sollen ihre Mahlzeiten per natürlicher Sprache oder Sprachnachricht loggen können, ohne klassische App-Formulare, Suchmasken oder manuelle Lebensmitteleingaben nutzen zu müssen.

Beispiel:

```text
250g Skyr, eine Banane und 30g Whey
```

oder:

```text
Ich hatte gerade eine Bowl mit Hähnchen und Reis
```

Der Tracker erkennt Lebensmittel, Mengen, Portionsgrößen und Mahlzeitentypen, berechnet Kalorien und Makronährstoffe und speichert alles in einer Datenbank. Der entscheidende Produktvorteil ist nicht nur AI-Erkennung, sondern eine lernende Nutrition Intelligence Engine, die bei unklaren Mahlzeiten kontrolliert schätzt, gezielt nachfragt und persönliche Gewohnheiten des Nutzers speichert.

---

## 2. Produktversprechen

Der Tracker soll nicht perfekte wissenschaftliche Genauigkeit versprechen. Das realistische Produktversprechen lautet:

> Der schnellste Weg, Ernährung ungefähr genau genug zu tracken — ohne App-Gefummel.

Das System soll:

- schnell sein
- natürlich bedienbar sein
- nicht nerven
- ausreichend genaue Schätzungen liefern
- transparent machen, wenn etwas geschätzt wurde
- persönliche Gewohnheiten lernen
- bei Unsicherheit kurz und intelligent nachfragen

---

## 3. Zielgruppe für erste Kundenversion

Die erste Version richtet sich an Nutzer, die bereits grundsätzlich an Ernährung, Fitness, Abnehmen, Muskelaufbau oder Makrotracking interessiert sind, aber klassische Tracker als zu umständlich empfinden.

Typische Nutzerprobleme:

- klassische Apps sind zu langsam
- Lebensmittelsuche nervt
- Portionsgrößen sind schwer einzuschätzen
- Voice Logging fehlt oder ist schlecht
- wiederkehrende Mahlzeiten müssen immer neu eingetragen werden
- ungenaue Mahlzeiten wie Bowl, Döner, Pasta oder Restaurantessen sind schwer zu tracken

---

## 4. Kernprinzip

Der Bot darf nicht einfach blind raten.

Die Systemlogik lautet:

```text
LLM = versteht die natürliche Sprache
Rule Parser = erkennt einfache strukturierte Eingaben schnell
Portion Engine = entscheidet, wie viel etwas wahrscheinlich war
Confidence Engine = entscheidet, ob gespeichert oder nachgefragt wird
User Memory = lernt persönliche Gewohnheiten
Clarification Flow = fragt kurz und sinnvoll nach
Nutrition Cache = reduziert API-Abhängigkeit und verbessert Geschwindigkeit
```

---

## 5. High-Level Architektur

```text
Telegram Bot
   ↓
Bot/API Service
   ↓
Input Processor
   ├── Text Handler
   └── Voice Handler
          ↓
       Speech-to-Text Worker
   ↓
Nutrition Intelligence Engine
   ├── Preprocessing
   ├── Rule Parser
   ├── LLM Parser
   ├── Portion Intelligence Layer
   ├── Nutrition Matcher
   ├── Confidence Engine
   └── Clarification Flow
   ↓
PostgreSQL Database
   ↓
Telegram Response
```

---

## 6. Zentrale Module

### 6.1 Telegram Bot

Der Telegram Bot ist das erste User Interface. Er empfängt Text- und Sprachnachrichten, sendet Rückfragen über Buttons und zeigt Tagesübersichten.

Wichtige Bot-Funktionen:

- `/start`
- `/help`
- `/today`
- `/goal`
- `/delete_last`
- `/edit_last`
- `/favorites`
- freie Texteingabe für Mahlzeiten
- Voice Message Logging
- Inline Buttons für Rückfragen

---

### 6.2 Rule Parser

Der Rule Parser erkennt einfache, häufige Muster ohne LLM.

Beispiele:

```text
250g Skyr
30g Whey
2 Eier
500ml Cola Zero
1 Banane
```

Ziel:

- Kosten reduzieren
- Latenz reduzieren
- LLM nur bei komplexen Eingaben nutzen
- deterministische Ergebnisse für einfache Fälle liefern

---

### 6.3 LLM Parser

Das lokale LLM wird nur eingesetzt, wenn die Eingabe komplexer ist oder der Rule Parser keine hohe Confidence erreicht.

Beispiele:

```text
Ich hatte heute Morgen zwei Scheiben Brot mit Käse und einen Kaffee mit Milch
```

Ausgabe soll strukturiertes JSON sein:

```json
{
  "meal_type": "breakfast",
  "items": [
    {
      "name": "Brot",
      "quantity": 2,
      "unit": "slice",
      "notes": null
    },
    {
      "name": "Käse",
      "quantity": null,
      "unit": "unknown",
      "notes": "on bread"
    },
    {
      "name": "Milch",
      "quantity": null,
      "unit": "unknown",
      "notes": "in coffee"
    }
  ]
}
```

Das LLM soll keine Kalorien erfinden. Es extrahiert nur Struktur.

---

### 6.4 Portion Intelligence Layer

Das ist der wichtigste Produktbaustein.

Er entscheidet, wie eine ungenaue Portion interpretiert wird.

Beispiele:

```text
eine Banane → 120g
ein Ei → 60g
eine Scheibe Toast → 25g
ein Glas Milch → 250ml
ein Teller Pasta normal → 350g
eine Portion Reis gekocht → 180g
```

Bei Unsicherheit erzeugt dieser Layer Optionen für eine Rückfrage.

Beispiel:

```text
User: ein Teller Pasta

Bot:
Welche Portion passt?

[ Klein ] [ Normal ] [ Groß ] [ Eigene Menge ]
```

---

### 6.5 Confidence Engine

Jeder erkannte Eintrag bekommt eine Confidence.

Vorgeschlagene Regeln:

```text
0.85 - 1.00 → direkt speichern
0.70 - 0.84 → speichern, aber als Schätzung markieren
0.50 - 0.69 → kurze Auswahlfrage stellen
unter 0.50 → gezielte Rückfrage erzwingen
```

Beispiele:

```text
250g Skyr → hohe Confidence → direkt speichern
eine Banane → hohe Confidence, Standardwert → direkt speichern
ein Teller Pasta → mittlere Confidence → Portionsgröße abfragen
eine Bowl → niedrige Confidence → Bowl-Typ abfragen
```

---

### 6.6 Clarification Flow

Der Bot soll bei Unsicherheit kurze Rückfragen stellen. Pro Schritt maximal eine Frage.

Schlecht:

```text
Wie viel Gramm Pasta? Welche Sauce? War Öl dabei? Gab es Käse?
```

Gut:

```text
Welche Portion passt?

[ Klein ] [ Normal ] [ Groß ] [ Eigene Menge ]
```

Für komplexe Mahlzeiten:

```text
Welche Bowl passt am ehesten?

[ Reis + Hähnchen ] [ Salat + Hähnchen ] [ Poke/Fisch ] [ Andere ]
```

Ziel:

- wenige Unterbrechungen
- hohe Nutzerkontrolle
- transparente Schätzungen
- kein Gefühl von Fehlern

---

### 6.7 User Portion Memory

Das System lernt persönliche Gewohnheiten.

Beispiel:

```text
User: eine Schüssel Haferflocken
Bot: Wie viel Gramm sind bei dir ungefähr eine Schüssel?
User: 80g
```

Danach:

```text
eine Schüssel Haferflocken → 80g für diesen User
```

Dadurch wird das Produkt mit der Zeit schneller und persönlicher.

---

### 6.8 Meal Templates

Nutzer sollen Standardmahlzeiten speichern können.

Beispiele:

```text
mein Standardfrühstück
mein Post-Workout-Shake
meine Chicken Bowl
mein usual lunch
```

Der Bot soll wiederkehrende Mahlzeiten erkennen und schnell loggen können.

---

### 6.9 Nutrition Matcher

Der Nutrition Matcher sucht Nährwerte in dieser Reihenfolge:

1. eigener Nutrition Cache
2. User-spezifische gespeicherte Lebensmittel
3. Open Food Facts für Markenprodukte und Barcodes
4. USDA FoodData Central für generische Lebensmittel
5. interne Default-Foods für häufige Lebensmittel
6. Rückfrage oder Admin Review bei niedrigem Match

Das System soll externe APIs nicht bei jedem Log erneut abfragen, sondern Ergebnisse cachen.

---

### 6.10 Voice Logging

Voice ist ein wichtiges Komfortfeature, aber technisch teurer als Text.

Ablauf:

```text
Telegram Voice Message
   ↓
Audio herunterladen
   ↓
Speech-to-Text Worker
   ↓
Transkript
   ↓
gleiche Nutrition Engine wie Text
```

Voice Processing soll asynchron über einen Worker laufen, damit der Bot nicht blockiert.

---

### 6.11 Admin Dashboard

Für echte Kundentests ist ein internes Dashboard notwendig.

Es soll zeigen:

- Anzahl Logs pro Tag
- aktive Nutzer
- häufig nicht erkannte Lebensmittel
- häufige Rückfragen
- fehlerhafte Food Matches
- Voice-Fehler
- LLM-Fehler
- API-Fehler
- manuell zu prüfende Items
- Top-Lebensmittel und Top-Mahlzeiten

Das Dashboard ist wichtig, damit die Engine wöchentlich verbessert werden kann.

---

## 7. Datenmodell Übersicht

Wichtige Tabellen:

```text
users
user_goals
food_logs
food_log_items
nutrition_items
food_aliases
portion_rules
user_portion_memory
meal_templates
meal_template_items
conversation_states
clarification_questions
audit_events
api_request_logs
error_logs
```

---

## 8. Nicht-Ziele für die erste Kundenversion

Nicht in Version 1 enthalten:

- eigene Mobile App
- Barcode Scanner
- Foto-Erkennung von Mahlzeiten
- Payment/Subscription
- Wearable Integration
- Apple Health / Google Fit
- Coaching Dashboard für Trainer
- komplexe Wochenberichte mit Charts
- automatische Diätplanung
- Rezeptgenerator

Diese Funktionen gehören später zur größeren Vision, aber nicht zur ersten ready-to-use Tracker-Version.

---

## 9. Must-Have Funktionen für erste Kundenversion

Die erste Kundenversion muss enthalten:

- Telegram User Onboarding
- Text Logging
- Voice Logging
- Rule Parser
- lokaler LLM Parser mit JSON Output
- Portion Intelligence
- Confidence Engine
- Clarification Flow mit Buttons
- User Portion Memory
- Meal Templates
- Nutrition Cache
- Open Food Facts Integration
- USDA FoodData Central Integration
- Tagesübersicht
- Kalorienziel
- Proteinziel
- letzten Eintrag löschen
- letzten Eintrag bearbeiten
- Error Logging
- Admin Dashboard light
- Backups

---

## 10. Erfolgsmetriken für Beta

Wichtige Produktmetriken:

- Logs pro aktivem Nutzer pro Tag
- Anteil erfolgreicher Logs ohne Rückfrage
- Anteil Logs mit Rückfrage
- Anteil abgebrochener Clarification Flows
- durchschnittliche Zeit bis Log gespeichert ist
- Korrekturrate nach Speicherung
- häufigste nicht erkannte Foods
- Nutzerbindung nach 3, 7 und 14 Tagen
- Voice-Nutzung
- Fehlerquote bei Voice
- LLM-Fallback-Rate

---

## 11. Strategische Vision

Phase 1 ist der Nutrition Tracker.

Langfristig kann daraus ein größerer Personal Nutrition Assistant entstehen:

- Ernährungstracking
- Gewichtsverlauf
- Zielmanagement
- Coach-Kommunikation
- personalisierte Empfehlungen
- Mahlzeitenplanung
- Einkaufsvorschläge
- Rezeptvorschläge
- Integration mit Wearables
- AI Coach für Fitness und Ernährung
- B2C und später eventuell B2B für Coaches

Aber Phase 1 muss extrem gut darin sein, Mahlzeiten natürlich, schnell und ausreichend genau zu loggen.

---

## 12. Kernthese

Die Kerninnovation ist nicht das LLM.

Die Kerninnovation ist:

```text
kontrolliertes Schätzen
+ intelligente Rückfragen
+ persönliche Lernlogik
+ gute Standardportionen
+ transparenter Confidence Score
```

Wenn diese Logik gut ist, reicht ein kleineres lokales Modell. Wenn diese Logik schlecht ist, hilft auch ein sehr starkes LLM nicht.
