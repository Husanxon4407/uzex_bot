# Project: UZEX AI Hackathon 2026 - qualifying round bot

## Goal
Telegram bot that answers questions (Russian or Uzbek) about exchange deals, ONLY from the data.
- Deadline: submit Google Form before 5 Nov 2026, 18:00 Tashkent. After 18:00 nothing can change.
- Judges ask 10 surprise questions, max 90 seconds per answer.
- If the bot invents a number, company or product that is not in the data -> team is eliminated.
- Score: 60 correct answers, 20 prototype quality (shows source, RU+UZ, fast), 20 written description.

## The owner is a beginner. Explain in simple English, step by step.

## How it works
question -> LLM writes DuckDB SQL -> run_sql (read-only) -> LLM writes answer ONLY from rows -> reply + SQL shown.
- LLM: Google Gemini API, free tier, via the OpenAI-compatible endpoint (see .env: MODEL, FALLBACK_MODEL).
- Database: uzex.duckdb, made by `python load_data.py` from folder uzex_spot_data/ (10 CSV files).

## Files
- load_data.py  - loads CSVs, fixes numbers ("304 547 938.4") and dates (DD.MM.YYYY), English column names,
                  creates view deals_full (deals + currency, volume = lots*lot_size, unit_price, amount_uzs).
- bot.py        - Telegram bot. SCHEMA = instructions for SQL. ANSWER_RULES = instructions for answers.
- test_questions.txt - practice questions, including "no answer" traps.
- .env          - secret keys (never commit).

## Data traps (keep these rules in SCHEMA)
- 500,000 deals, 03.01.2022 - 30.10.2026. Nothing before 2022.
- Regions: deals/participants use Uzbek Latin ('Namangan viloyati'); contracts use Russian ('Наманганская область').
- Same product written many ways (697 names): search with ILIKE '%stem%'.
- 148 contracts in USD (export). amount_uzs converts with the rate on the deal date.
- Status 'Аннулирован(Не оплачен)' = cancelled, the deal did not happen; exclude from sales totals.
- Volume = lots * lot_size; never add tonnes and kilograms.
- Company names: Cyrillic and Latin, with quotes; deals only have INN, join participants.

## Workflow
1. Ask the bot a test question. 2. Check the right answer with our own SQL in DuckDB.
3. If wrong: add a rule or an example to SCHEMA in bot.py. 4. Restart bot, ask again.
Only ONE copy of the bot may run at a time (same token).
