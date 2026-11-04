import os, re, json, time, html, asyncio, duckdb
from dotenv import load_dotenv
from openai import OpenAI
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

load_dotenv()
# Works with Gemini through Google's OpenAI-compatible address, or with OpenAI.
# max_retries=0: no hidden automatic retries (they made one call take up to ~105 s).
client = OpenAI(api_key=os.environ["AI_API_KEY"],
                base_url=os.environ.get("AI_BASE_URL") or None,
                max_retries=0)
CALL_TIMEOUT = 20     # seconds one AI call may take before we switch to the fallback model
TOTAL_BUDGET = 75     # seconds for the whole answer (judges allow 90)
MODEL = os.environ["MODEL"]   # copy the exact model name from Google AI Studio
db = duckdb.connect("uzex.duckdb", read_only=True)

# ---------- 1. Describe the database to the AI ----------
def values(sql):
    return ", ".join(str(r[0]) for r in db.execute(sql).fetchall())

SCHEMA = f"""
You write DuckDB SQL for a commodity exchange database (invented data, 03.01.2022 - 30.10.2026).

TABLES
deals_full  -- one row per deal. USE THIS TABLE FOR MOST QUESTIONS.
  deal_id, deal_date DATE, deal_time, auction_type, lots (number of lots), amount (in contract currency),
  start_price, contract_id, product (product name + attributes), lot_size, unit, region (seller warehouse region),
  contract_type, contract_form, status, seller_inn, buyer_inn, seller_broker, buyer_broker,
  paid_date, delivered_date, lots_delivered,
  volume (= lots * lot_size, in `unit`), unit_price (= amount / volume, contract currency),
  currency, product_group, category, industry, amount_uzs (amount converted to so'm on the deal date)
contracts(contract_id, product_name, brand, size, grade, type, class, hs_code, product_group, category, industry,
  unit, lot_size, currency, base_price, deposit, delivery_basis, region_ru, warehouse_address, auction_type,
  contract_type, contract_form, payment_days, delivery_days, packaging, seller_inn, registered_date, valid_until)
participants(inn, name, region, activity, role, vat_payer)   -- companies; join deals.seller_inn / buyer_inn = inn
brokers(broker_code, name, inn, region)                       -- join deals.seller_broker / buyer_broker = broker_code
usd_rates(rate_date, uzs_per_usd)

EXACT VALUES
status: {values("select distinct status from deals")}
  'Аннулирован(Не оплачен)' = cancelled, the deal did NOT happen.
region (deals, participants, brokers): {values("select distinct region from deals")}
region_ru (contracts only): {values("select distinct region_ru from contracts")}
unit: {values("select distinct unit from deals")}
auction_type: {values("select distinct auction_type from deals")}
contract_type: {values("select distinct contract_type from deals")}
contract_form: {values("select distinct contract_form from deals")}
currency: {values("select distinct currency from contracts")}
industry: {values("select distinct industry from contracts")}
category: {values("select distinct category from contracts")}

RULES
- Return ONLY one SQL SELECT query, no explanation.
- Products are written in many ways: search with ILIKE '%word%' on a short word stem
  (e.g. '%сахар%', '%дизел%', '%пшениц%'), never with = on the full name.
- Company names: search participants.name with ILIKE, try both Cyrillic and Latin spelling if unsure.
- Map regions from Uzbek/Russian/English to the exact values above (Наманган = 'Namangan viloyati').
- For "sold", "trade volume", "total amount", "price" exclude cancelled deals (status <> 'Аннулирован(Не оплачен)')
  unless the user asks about cancelled deals.
- For "how many deals" (сколько сделок / nechta bitim / qancha bitim tuzgan), a cancelled deal WAS still concluded.
  Return BOTH numbers: COUNT(*) AS all_deals, COUNT(*) FILTER (WHERE status = 'Аннулирован(Не оплачен)') AS cancelled.
  Same for "which broker/company has the most deals": rank by COUNT(*) of all deals.
- A broker takes part in a deal as seller_broker OR buyer_broker; a company as seller_inn OR buyer_inn.
  Unless the question says seller/buyer side, count BOTH sides, each deal once. Example:
    SELECT b.broker_code, b.name, COUNT(*) AS all_deals,
           COUNT(*) FILTER (WHERE d.status = 'Аннулирован(Не оплачен)') AS cancelled
    FROM deals_full d JOIN brokers b ON b.broker_code IN (d.seller_broker, d.buyer_broker)
    GROUP BY 1, 2 ORDER BY all_deals DESC LIMIT 5
- Average price of a product: weighted = SUM(amount) / SUM(volume), GROUP BY unit, currency only
  (NOT by product name - the same product has many spellings). Also return COUNT(*) and list(DISTINCT product).
- If the question asks about dates outside 2022-01-03 .. 2026-10-30, still run the query (it returns nothing).
- Money totals across currencies: use amount_uzs. Never add tonnes and kilograms together; group by unit.
- When you filter by product, also return the matched product names (e.g. list(DISTINCT product)) so they can be shown.
- Always add LIMIT 50.
"""

ANSWER_RULES = """You answer questions about a commodity exchange database.
You get the user question, the SQL that was run and its result rows.
- Answer ONLY from the result rows. Never add numbers, companies or products that are not in the rows.
- If the rows are empty or do not answer the question, say clearly that the data has no answer.
- The data covers only 03.01.2022 - 30.10.2026. If the question asks about a period outside it (e.g. 2021),
  do NOT answer "0": say the data has no information for that period and that it starts on 03.01.2022.
- If a count or sum is 0 or NULL because nothing matched (e.g. a product not traded on the exchange),
  say the data has no such deals/product - do not present it as a real result.
- The data contains ONLY: deals (date, product, amount, volume, price, region, status, seller/buyer INN, brokers),
  contracts, company names/regions/activity, brokers, USD rates. It does NOT contain problems, events, news,
  reasons ("why"), opinions, forecasts, people (directors, employees), phone numbers, addresses of people.
  If the question asks for something it does not contain, FIRST say clearly that the data has no such information.
  Then you MAY add the closest facts from the rows, introduced as "the data only shows:" (e.g. for "problems":
  cancelled deals = not paid on time, partly delivered deals). Never present them as the full answer.
- If the rows give all deals and cancelled deals, state the total first, then how many were cancelled.
- If the rows give one price per unit (tonne, kilogram), give each one separately with its unit; never mix units.
- Mention only the filters that the SQL really used.
- If the SQL already excluded cancelled deals, do NOT report a cancelled count (it would wrongly be 0).
- Answer in the SAME language as the question (Uzbek or Russian).
- Be short. Format big numbers with spaces (1 234 567). Name the units and the currency.
- Mention important filters (for example: cancelled deals not counted, period, region).
FORMAT (it is shown in Telegram):
- First line: one short sentence with the main result, the key number in **bold**.
- Then, only if useful, up to 6 short lines starting with "- " (details: count, sum, product names, date).
- Last line: "ℹ️ " + the filters used (period, region, cancelled deals not counted), in one short line.
- Use only **bold** and "- " lists. No headings, no tables, no code, no SQL."""

# ---------- 2. Safety: only allow reading ----------
FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|create|alter|copy|attach|install|load|pragma|export)\b", re.I)

def run_sql(sql):
    sql = sql.strip().strip("`").removeprefix("sql").strip().rstrip(";")
    if not sql.lower().startswith(("select", "with")) or FORBIDDEN.search(sql):
        raise ValueError("Only SELECT queries are allowed")
    cur = db.cursor()
    rows = cur.execute(sql).fetchmany(50)
    cols = [d[0] for d in cur.description]
    return sql, cols, rows

# Backup models, used if the main model is busy. Several allowed, comma-separated in .env.
# On the free tier every model has its own limit, so more backups = more questions per minute.
FALLBACK_MODELS = [m.strip() for m in os.environ.get("FALLBACK_MODEL", "").split(",") if m.strip()]
resting_until = {}     # model -> time; a model that said "too many requests" (429) rests for 60 s

def ask_llm(system, user, deadline):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    models = [MODEL] + FALLBACK_MODELS
    while deadline - time.time() > 3:
        ready = [m for m in models if resting_until.get(m, 0) <= time.time()]
        if not ready:
            # every model is over its per-minute limit: wait (max 10 s at a time) and try again
            wake = min(resting_until[m] for m in models)
            time.sleep(max(1, min(10, wake - time.time(), deadline - time.time() - 3)))
            continue
        for model in ready:
            left = deadline - time.time()
            if left < 3:
                break
            try:
                r = client.chat.completions.create(model=model, temperature=0, messages=messages,
                                                   timeout=min(CALL_TIMEOUT, left))
                return r.choices[0].message.content.strip()
            except Exception as e:
                print(f"AI error with {model}: {str(e)[:200]}")
                # 429 = too many requests: rest this model. Other errors: short rest.
                resting_until[model] = time.time() + (20 if "429" in str(e) else 5)
    raise RuntimeError("AI is not available right now")

def rows_as_text(cols, rows):
    """Last resort if the AI can't write the answer: show the database rows themselves."""
    if not rows:
        return "Ma'lumotlarda bunday ma'lumot topilmadi. / В данных такой информации нет."
    lines = [" | ".join(cols)] + [" | ".join(str(v) for v in r) for r in rows[:20]]
    return "Natija / Результат:\n" + "\n".join(lines)

# ---------- 3. Question -> SQL -> rows -> answer ----------
def answer(question):
    deadline = time.time() + TOTAL_BUDGET
    prompt, rows = question, None
    for attempt in range(3):                       # try up to 3 times if the SQL fails
        try:
            sql = ask_llm(SCHEMA, prompt, deadline)
        except RuntimeError:
            break                                  # AI not reachable in time
        try:
            sql, cols, rows = run_sql(sql)
            break
        except Exception as e:
            prompt = f"{question}\n\nYour previous SQL:\n{sql}\nfailed with error:\n{e}\nWrite a corrected query."
    if rows is None:
        return "Kechirasiz, savolni qayta ishlab bo'lmadi. / Извините, не удалось обработать вопрос.", None

    result = json.dumps({"columns": cols, "rows": rows}, ensure_ascii=False, default=str)
    try:
        text = ask_llm(ANSWER_RULES, f"Question: {question}\nSQL: {sql}\nResult: {result[:15000]}",
                       deadline + 10)              # a little extra time for the final answer
    except RuntimeError:
        text = rows_as_text(cols, rows)            # AI busy: still answer, straight from the data
    return text, sql                               # the answer text and the SQL that produced it

# ---------- 4. Telegram: nice formatting ----------
LABELS = {  # words shown around the answer, in the question's language
    "uz": {"title": "📊 <b>Javob</b>", "source": "Manba", "registry": "UZEX bitimlar reyestri",
           "sql": "🔎 <b>SQL so'rov:</b>", "show": "🔎 SQL so'rovni ko'rsatish", "hide": "🙈 SQL'ni yashirish",
           "old": "Bu eski xabar, savolni qayta yuboring."},
    "ru": {"title": "📊 <b>Ответ</b>", "source": "Источник", "registry": "Реестр сделок UZEX",
           "sql": "🔎 <b>SQL-запрос:</b>", "show": "🔎 Показать SQL-запрос", "hide": "🙈 Скрыть SQL",
           "old": "Это старое сообщение, отправьте вопрос ещё раз."},
}
SQL_OF_MESSAGE = {}   # Telegram message id -> (closed text, opened text, language), for the SQL button

def language(text):
    """Russian if the question is in Cyrillic without Uzbek letters (ў қ ғ ҳ), otherwise Uzbek."""
    cyr = len(re.findall(r"[а-яё]", text.lower()))
    return "ru" if cyr > len(text) * 0.3 and not re.search(r"[ўқғҳ]", text.lower()) else "uz"

def md_to_html(t):
    """The AI writes **bold** and '- ' lists; Telegram needs HTML. Escape everything else."""
    t = html.escape(t, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?m)^\s*[\*\-•]\s+", "• ", t)           # list lines -> bullets
    t = re.sub(r"(?m)^#+\s*(.+)$", r"<b>\1</b>", t)      # headings -> bold
    t = re.sub(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = t.replace("`", "")
    return re.sub(r"\n{3,}", "\n\n", t).strip()

def tables_used(sql):
    names = re.findall(r"\b(?:from|join)\s+(deals_full|deals|contracts|participants|brokers|usd_rates)\b", sql, re.I)
    return ", ".join(dict.fromkeys(n.lower() for n in names))

def sql_button(lang, opened):
    L = LABELS[lang]
    return InlineKeyboardMarkup([[InlineKeyboardButton(L["hide"] if opened else L["show"],
                                                       callback_data="sql_hide" if opened else "sql_show")]])

async def send_answer(update, question, text, sql, seconds):
    """Answer with a 'Show SQL' button. If Telegram rejects the formatting, send plain text."""
    lang = language(question)
    L = LABELS[lang]
    body = md_to_html(text)
    try:
        if sql is None:                              # error message: no source, no button
            await update.message.reply_text(f"⚠️ {body}", parse_mode="HTML")
            return
        closed = (f"{L['title']}\n\n{body}\n\n━━━━━━━━━━━━━━\n"
                  f"📁 <b>{L['source']}:</b> {L['registry']} · {html.escape(tables_used(sql))}\n⏱ {seconds:.1f} s")
        opened = f"{closed}\n\n{L['sql']}\n<pre><code class=\"language-sql\">{html.escape(sql, quote=False)}</code></pre>"
        if len(closed) > 4000:
            raise BadRequest("answer too long for one message")
        msg = await update.message.reply_text(closed, parse_mode="HTML", reply_markup=sql_button(lang, False))
        SQL_OF_MESSAGE[msg.message_id] = (closed, opened, lang)
    except BadRequest as e:
        print(f"Telegram rejected the formatting ({e}); sending plain text")
        plain = text if sql is None else f"{text}\n\n— SQL —\n{sql}"
        for k in range(0, len(plain), 4000):
            await update.message.reply_text(plain[k:k + 4000])

async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """'Show SQL' / 'Hide SQL' button was pressed: open or close the SQL in the same message."""
    q = update.callback_query
    saved = SQL_OF_MESSAGE.get(q.message.message_id)
    if not saved:                                    # bot was restarted since this answer
        await q.answer(LABELS[language(q.message.text or "")]["old"], show_alert=True)
        return
    closed, opened, lang = saved
    show = q.data == "sql_show"
    await q.answer()
    try:
        if show and len(opened) > 4000:              # too long to fit: send the SQL as its own message
            await q.message.reply_text(opened[len(closed):].strip(), parse_mode="HTML")
            return
        await q.edit_message_text(opened if show else closed, parse_mode="HTML",
                                  reply_markup=sql_button(lang, show))
    except BadRequest as e:
        print(f"Button edit failed: {e}")

async def keep_typing(chat):
    """Telegram shows 'typing...' for only ~5 s, so repeat it every 4 s until the answer is ready."""
    while True:
        try:
            await chat.send_action("typing")
        except Exception:
            pass
        await asyncio.sleep(4)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 <b>Salom!</b> Birja bitimlari bo'yicha savol bering (o'zbek yoki rus tilida).\n"
        "👋 <b>Здравствуйте!</b> Задайте вопрос о биржевых сделках (на русском или узбекском).\n\n"
        "📁 <i>Ma'lumotlar / Данные: 03.01.2022 – 30.10.2026</i>", parse_mode="HTML")

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    question = update.message.text
    typing = asyncio.create_task(keep_typing(update.message.chat))
    t = time.time()
    try:
        text, sql = await asyncio.wait_for(asyncio.to_thread(answer, question), timeout=88)
    except asyncio.TimeoutError:
        text, sql = "Javob juda uzoq davom etdi, qayta urinib ko'ring. / Слишком долго, попробуйте ещё раз.", None
    except Exception as e:
        print(f"Unexpected error: {e}")
        text, sql = "Kechirasiz, xatolik yuz berdi. / Извините, произошла ошибка.", None
    finally:
        typing.cancel()                              # stop 'typing...' when the answer is ready
    await send_answer(update, question, text, sql, time.time() - t)

if __name__ == "__main__":       # runs only with "python bot.py" (lets tests import answer())
    app = Application.builder().token(os.environ["TELEGRAM_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.add_handler(CallbackQueryHandler(on_button))   # the "Show SQL / Hide SQL" button
    print("Bot is running...")
    app.run_polling()
