# UZEX AI Hackathon 2026 — Telegram bot (team handover guide)

A Telegram bot that answers questions **in Uzbek or Russian** about exchange deals, **only from the UZEX data**
(03.01.2022 – 30.10.2026, 500 000 deals). Every number comes from a SQL query on the data, never from the AI's memory.

> ⚠️ **The most important rule of the hackathon:** if the bot invents a number, company or product that is
> not in the data, the team is eliminated. Every change you make must keep that true. Test after every change.

---

## 1. What has been done (status on 05.11.2026)

- ✅ Data loaded and checked: 500 000 deals, 0 broken numbers or dates, every deal links to its contract, company, broker.
- ✅ Bot works in Telegram, answers in the question's language (Uzbek → Uzbek, Russian → Russian).
- ✅ **20 test questions** (including 7 "no data" traps) — the bot's answers were compared with correct answers
  we computed with our own SQL: **all match**. See `test_questions.txt` and `test_answers.txt`.
- ✅ Nice Telegram layout: header, answer with bold numbers, source line, time, and a **"Show SQL" button**.
- ✅ Speed/reliability: usually 2–10 s per answer, hard limit 75 s (judges allow 90 s). If the main AI model is
  busy, the bot switches to backup models, and waits/retries if all are busy.
- ✅ Written description for the Google Form: `description.txt` (Uzbek + short Russian).

## 2. How it works

```
question → Gemini writes one SQL SELECT → DuckDB runs it (read-only) → Gemini writes the answer ONLY from the rows
        → Telegram: answer + source + "Show SQL" button
```

| File | What it is |
|---|---|
| `bot.py` | The bot. **`SCHEMA`** = rules for writing SQL. **`ANSWER_RULES`** = rules for writing answers. Most fixes go there. |
| `load_data.py` | Builds the database `uzex.duckdb` from `uzex_spot_data/` (10 CSV files). |
| `uzex_spot_data/` | The original data + its `README.md` (explains every column and status). |
| `test_bot.py` | Asks the bot the test questions without Telegram and prints answers + time. |
| `test_questions.txt` / `test_answers.txt` | Practice questions and their **correct** answers. |
| `description.txt` | Written description for the Google Form. |
| `.env.example` | Template for the secret keys file `.env`. |
| `CLAUDE.md` | Short project notes and data traps. |

## 3. Setup on your computer (Windows, ~10 minutes)

1. Install **Python 3.12 or newer** (python.org → tick "Add Python to PATH") and **Git** (git-scm.com).
2. Download the code (you must be invited to the repo first):
   ```
   git clone https://github.com/Husanxon4407/uzex_bot.git
   cd uzex_bot
   ```
3. Install packages:
   ```
   pip install -r requirements.txt
   ```
4. Build the database (takes ~10 seconds, must print `deals 500000`, `bad amounts: 0`, `bad dates: 0`):
   ```
   python load_data.py
   ```
5. Create the secret keys file: copy `.env.example` to a new file named **`.env`** and paste the real
   `TELEGRAM_TOKEN` and `AI_API_KEY` (ask Husanxon — the keys are sent privately, never in a group chat). **Never upload `.env`.**
6. Start the bot:
   ```
   python bot.py
   ```
   It prints `Bot is running...`. Open the bot in Telegram and send `/start`. Stop it with **Ctrl + C**.

> ⚠️ **Only ONE copy of the bot may run at a time** (same token). If two computers run it, Telegram gives
> a "Conflict" error and answers get lost. Agree in the team chat who is running it.

## 4. How to test

- Without Telegram: `python test_bot.py` (all questions) or `python test_bot.py 4 10` (only questions 4 and 10).
- Compare every answer with `test_answers.txt`. Numbers must match exactly.
- "No data" traps (2021, iPhone, director, gas in Europe, wheat in Samarkand 2023, "problems", "why") — the bot
  must clearly say the data has no such information, and must **never** invent a number.
- To check a correct answer yourself, run your own SQL:
  ```
  python -c "import duckdb; print(duckdb.connect('uzex.duckdb', read_only=True).sql(\"SELECT COUNT(*) FROM deals WHERE year(deal_date)=2023\"))"
  ```
- ⚠️ The Gemini key is on the **free tier** (limited requests per minute and per day). Don't run long test
  sessions shortly before the judges start.

## 5. How to change something

1. Find the wrong answer, and compute the correct answer with your own SQL.
2. In `bot.py`, add a short rule or example to `SCHEMA` (if the SQL was wrong) or `ANSWER_RULES` (if the text was wrong).
3. Run `python test_bot.py` — check the fixed question **and** that the other answers are still correct.
4. Restart the bot (Ctrl + C, then `python bot.py`).
5. If you change something in the data loading, run `python load_data.py` again.

## 6. Sharing changes with the team (Git)

```
git pull                         # get the newest version first, ALWAYS
# ... edit files, test ...
git add bot.py test_questions.txt
git commit -m "Short description of the change"
git push
```
The person running the bot then does: Ctrl + C → `git pull` → `python bot.py`.

## 7. During the judging

- 10 surprise questions, max 90 seconds per answer.
- The computer running the bot must stay **on, awake and online**
  (Settings → System → Power → "When plugged in, put my device to sleep" → **Never**).
- Don't change code during the judging.
- If the bot stops answering: look at the terminal for errors, press Ctrl + C, and run `python bot.py` again.

## 8. Data traps (already handled in the rules — keep them)

- No data before 03.01.2022 or after 30.10.2026.
- Regions: deals/participants in Uzbek Latin (`Namangan viloyati`), contracts in Russian (`Наманганская область`).
- One product has many spellings → search with `ILIKE '%stem%'` (e.g. `'%сахар%'`, `'%дизел%'`).
- `Аннулирован(Не оплачен)` = cancelled, the deal did not happen → not counted in sales/volume/price.
  For "how many deals", give the total and the cancelled count separately.
- Volume = lots × lot_size. Never add tonnes and kilograms. Average price = SUM(amount) / SUM(volume), per unit.
- Export deals are in USD; `amount_uzs` converts them with the dollar rate on the deal date.
