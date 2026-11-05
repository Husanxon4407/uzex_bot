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
- ✅ **The bot runs 24/7 on our server** (MyCloud, Tashkent) — nobody's laptop needs to be on. See section 9.

> 🔗 **Bot link (for testing and for the form): https://t.me/uzex_birja_ai_bot**

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

> ℹ️ **You only need this to test or change the code locally.** The real bot already runs on the server
> (section 9). To just ask the bot questions, open https://t.me/uzex_birja_ai_bot — no setup needed.
> ⚠️ **Do NOT start the bot (`start_bot.bat` / `python bot.py`) while the server runs it** — two copies with the
> same token conflict and answers get lost. To test locally, use `python test_bot.py` (it does not use Telegram).

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
6. Start the bot: **double-click `start_bot.bat`** (recommended). A black window opens and prints
   `Bot is running...`. Keep that window open; **closing it stops the bot**. If the bot crashes, it
   restarts by itself after 5 seconds. It also builds the database first if `uzex.duckdb` is missing.
   (Or in a terminal: `python bot.py`, stop with **Ctrl + C**.)
   Then open **https://t.me/uzex_birja_ai_bot** in Telegram and send `/start`.

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
Pushing to GitHub does **not** change the running bot. To put a change live, it must be copied to the
server (section 9 → "Put a change live").

## 7. During the judging

- 10 surprise questions, max 90 seconds per answer.
- The bot runs on the server, so laptops can be closed. Just check before judging that it answers in Telegram.
- Make sure the **MyCloud balance** covers the judging days (it bills per day; the server stops at 0).
- Don't change code during the judging.
- If the bot stops answering: see section 9 → "If the bot does not answer".

## 8. Data traps (already handled in the rules — keep them)

- No data before 03.01.2022 or after 30.10.2026.
- Regions: deals/participants in Uzbek Latin (`Namangan viloyati`), contracts in Russian (`Наманганская область`).
- One product has many spellings → search with `ILIKE '%stem%'` (e.g. `'%сахар%'`, `'%дизел%'`).
- `Аннулирован(Не оплачен)` = cancelled, the deal did not happen → not counted in sales/volume/price.
  For "how many deals", give the total and the cancelled count separately.
- Volume = lots × lot_size. Never add tonnes and kilograms. Average price = SUM(amount) / SUM(volume), per unit.
- Export deals are in USD; `amount_uzs` converts them with the dollar rate on the deal date.

---

## 9. The server (where the bot runs 24/7)

| | |
|---|---|
| Provider | MyCloud (mycloud.uz), Tashkent — billed **per day** from the account balance |
| Server | `212.47.58.91`, Ubuntu 24.04, 1 vCPU, 2 GB RAM |
| Login | `ssh root@212.47.58.91` — **SSH key only** (ask Husanxon to add your public key) |
| Bot folder | `/opt/uzex_bot` (code, data, `.env`, database `uzex.duckdb`, Python venv in `venv/`) |
| Runs as | system user `uzexbot` (not root); `.env` readable only by that user |
| Service | `uzex-bot` (systemd): starts on server boot, **restarts itself 5 s after a crash** |

### Everyday commands (run on the server after `ssh root@212.47.58.91`)
```
systemctl status uzex-bot            # is it running? (look for "active (running)")
journalctl -u uzex-bot -n 50         # last 50 log lines (AI errors, Telegram errors)
journalctl -u uzex-bot -f            # watch the log live (Ctrl + C to stop watching)
systemctl restart uzex-bot           # restart the bot
systemctl stop uzex-bot              # stop the bot (e.g. before running it somewhere else)
systemctl start uzex-bot             # start it again
```
In the log, `AI error with gemini-3.5-flash: Error code: 429` is normal on the free tier — the bot then uses a
backup model automatically. A problem is only if the bot stops answering in Telegram.

### Put a change live (after testing it locally with `python test_bot.py`)
From your computer, in the bot folder (Git Bash or PowerShell):
```
scp bot.py root@212.47.58.91:/opt/uzex_bot/bot.py
ssh root@212.47.58.91 "chown uzexbot:uzexbot /opt/uzex_bot/bot.py && systemctl restart uzex-bot && systemctl is-active uzex-bot"
```
It must print `active`. Then ask the bot one question in Telegram to confirm.
If you changed `load_data.py` or the data, also run on the server:
`cd /opt/uzex_bot && sudo -u uzexbot venv/bin/python load_data.py && systemctl restart uzex-bot`.
If you changed `requirements.txt`: `cd /opt/uzex_bot && sudo -u uzexbot venv/bin/pip install -r requirements.txt`.

### If the bot does not answer
1. `systemctl status uzex-bot` — if not `active`, run `systemctl restart uzex-bot` and read `journalctl -u uzex-bot -n 50`.
2. `Conflict: terminated by other getUpdates request` in the log = **someone else is running the bot**
   (a laptop with `start_bot.bat` or `python bot.py`). Find it and close it.
3. Server not reachable at all = check the MyCloud panel: is the server on, and is the balance above 0?
4. Too many failed SSH logins can block your IP for a while. Don't retry in a loop; wait, or unblock it
   from the MyCloud panel's web console.

### Emergency fallback
If the server is down and can't be fixed quickly, one person can run the bot on their own computer
(section 3, `start_bot.bat`). First make sure the server copy is stopped (`systemctl stop uzex-bot`), then
switch back later: close `start_bot.bat`, then `systemctl start uzex-bot`.
