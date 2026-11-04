import duckdb

DATA = "uzex_spot_data"          # folder with the CSV files
db = duckdb.connect("uzex.duckdb")

def num(col):   # "304 547 938.4" -> 304547938.4
    return f"TRY_CAST(REPLACE(REPLACE(\"{col}\", ' ', ''), chr(160), '') AS DOUBLE)"

def dt(col):    # "03.01.2022" -> date
    return f"TRY_STRPTIME(\"{col}\", '%d.%m.%Y')::DATE"

db.execute(f"""
CREATE OR REPLACE TABLE deals AS
SELECT
  "Номер сделки"::BIGINT        AS deal_id,
  {dt('Дата сделки')}           AS deal_date,
  "Время сделки"                AS deal_time,
  "Тип торгов"                  AS auction_type,
  {num('Количество')}           AS lots,
  {num('Сумма сделки')}         AS amount,
  {num('Стартовая цена')}       AS start_price,
  "Номер контракта"             AS contract_id,
  "Наименование товара"         AS product,
  {num('Лот')}                  AS lot_size,
  "Единица измерения"           AS unit,
  "Регион"                      AS region,
  "Тип контракта"               AS contract_type,
  "Форма контракта"             AS contract_form,
  "Состояние сделки"            AS status,
  "ИНН продавца"                AS seller_inn,
  "ИНН покупателя"              AS buyer_inn,
  "Брокер продавца"             AS seller_broker,
  "Брокер покупателя"           AS buyer_broker,
  {dt('Дата оплаты')}           AS paid_date,
  {dt('Дата поставки')}         AS delivered_date,
  {num('Поставлено')}           AS lots_delivered
FROM read_csv('{DATA}/deals_*.csv', all_varchar=true)
""")

db.execute(f"""
CREATE OR REPLACE TABLE contracts AS
SELECT
  "Номер контракта" AS contract_id, "Наименование продукта" AS product_name,
  "Марка товара" AS brand, "Размер товара" AS size, "Сорт товара" AS grade,
  "Тип товара" AS type, "Класс товара" AS class, "Код ТН ВЭД" AS hs_code,
  "Группа товара" AS product_group, "Категория товара" AS category,
  "Отрасль промышленности" AS industry, "Единица измерения" AS unit,
  {num('Лот')} AS lot_size, "Валюта" AS currency, {num('Базисная цена')} AS base_price,
  "Сумма залога" AS deposit, "Базис поставки" AS delivery_basis,
  "Регион" AS region_ru, "Адрес склада" AS warehouse_address,
  "Тип торгов" AS auction_type, "Тип контракта" AS contract_type,
  "Форма контракта" AS contract_form,
  TRY_CAST("Срок оплаты" AS INT) AS payment_days,
  TRY_CAST("Срок поставки" AS INT) AS delivery_days,
  "Упаковка" AS packaging, "ИНН продавца" AS seller_inn,
  {dt('Дата регистрации')} AS registered_date, {dt('Действует до')} AS valid_until
FROM read_csv('{DATA}/contracts.csv', all_varchar=true)
""")

db.execute(f"""
CREATE OR REPLACE TABLE participants AS
SELECT "ИНН" AS inn, "Наименование" AS name, "Регион" AS region,
       "Вид деятельности" AS activity, "Роль" AS role, "Плательщик НДС" AS vat_payer
FROM read_csv('{DATA}/participants.csv', all_varchar=true)
""")

db.execute(f"""
CREATE OR REPLACE TABLE brokers AS
SELECT "Код брокера" AS broker_code, "Наименование" AS name, "ИНН" AS inn, "Регион" AS region
FROM read_csv('{DATA}/brokers.csv', all_varchar=true)
""")

db.execute(f"""
CREATE OR REPLACE TABLE usd_rates AS
SELECT {dt('Дата')} AS rate_date, {num('Курс')} AS uzs_per_usd
FROM read_csv('{DATA}/usd_rates.csv', all_varchar=true)
""")

# One easy table for the AI: deals + contract currency + amount in so'm
db.execute("""
CREATE OR REPLACE VIEW deals_full AS
SELECT d.*,
       d.lots * d.lot_size                          AS volume,
       d.amount / NULLIF(d.lots * d.lot_size, 0)    AS unit_price,
       c.currency, c.product_group, c.category, c.industry,
       CASE WHEN c.currency = 'Доллар США' THEN d.amount * r.uzs_per_usd
            ELSE d.amount END                       AS amount_uzs
FROM deals d
LEFT JOIN contracts c ON c.contract_id = d.contract_id
LEFT JOIN usd_rates r ON r.rate_date = d.deal_date
""")

for t in ["deals", "contracts", "participants", "brokers", "usd_rates"]:
    print(t, db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
print("bad amounts:", db.execute("SELECT COUNT(*) FROM deals WHERE amount IS NULL").fetchone()[0])
print("bad dates:", db.execute("SELECT COUNT(*) FROM deals WHERE deal_date IS NULL").fetchone()[0])
