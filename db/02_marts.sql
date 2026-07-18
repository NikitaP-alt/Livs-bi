-- ============================================================
-- LIVS BI — витрины (marts) под дашборды Фазы 1 (задачи 3/4/6)
-- Обогащённые вьюхи: Metabase режет их фильтрами Год/Кв/Месяц/Клиент/ТТ/SKU.
-- ============================================================

CREATE SCHEMA IF NOT EXISTS marts;

-- Продажи (Sell-Out) — зад. 3
CREATE OR REPLACE VIEW marts.v_sellout AS
SELECT
    f.period,
    EXTRACT(YEAR  FROM f.period)::int          AS year,
    EXTRACT(MONTH FROM f.period)::int          AS month_num,
    EXTRACT(QUARTER FROM f.period)::int         AS quarter,
    c.client_id, c.name                         AS client,
    f.tt_id, dt.client_tt_code,
    COALESCE(dt.name, dt.client_tt_code)        AS tt,
    dt.chain_name,
    COALESCE(NULLIF(dt.city, ''), '(город не определён)') AS city,   -- вместо null на карточке «по городам»
    s.sku_id, s.livs_article, s.name            AS sku,
    COALESCE(p.name, s.name)                    AS product,
    f.qty,
    -- рубли из отчёта, иначе оценка по утверждённому прайсу (Цена с НДС) × кол-во
    COALESCE(f.rub_est, ROUND(f.qty * pp.price_vat, 2))::numeric(16,2) AS rub_est
FROM core.fact_sellout f
JOIN core.dim_client c ON c.client_id = f.client_id
LEFT JOIN core.dim_tt  dt ON dt.tt_id  = f.tt_id
JOIN core.dim_sku      s  ON s.sku_id  = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id
LEFT JOIN core.dim_product_price pp ON pp.product_id = s.product_id;

-- Закупки (Sell-In из 1С) — зад. 4
CREATE OR REPLACE VIEW marts.v_sellin AS
SELECT
    f.period,
    EXTRACT(YEAR  FROM f.period)::int          AS year,
    EXTRACT(MONTH FROM f.period)::int          AS month_num,
    EXTRACT(QUARTER FROM f.period)::int         AS quarter,
    c.client_id, c.name                         AS client,
    s.sku_id, s.livs_article, s.name            AS sku,
    COALESCE(p.name, s.name)                    AS product,
    f.qty, f.rub
FROM core.fact_sellin f
JOIN core.dim_client c ON c.client_id = f.client_id
JOIN core.dim_sku    s ON s.sku_id    = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id;

-- Остатки (все снимки) — зад. 6
CREATE OR REPLACE VIEW marts.v_stock AS
SELECT
    f.snapshot_date,
    EXTRACT(YEAR  FROM f.snapshot_date)::int    AS year,
    EXTRACT(MONTH FROM f.snapshot_date)::int     AS month_num,
    c.client_id, c.name                          AS client,
    f.tt_id, dt.client_tt_code,
    COALESCE(dt.name, dt.client_tt_code)         AS tt,
    dt.chain_name, dt.city,
    s.sku_id, s.livs_article, s.name             AS sku,
    COALESCE(p.name, s.name)                     AS product,
    CEIL(f.qty)::numeric(16,3) AS qty, f.rub_est   -- остатки округляем ВВЕРХ до целых упаковок
FROM core.fact_stock f
JOIN core.dim_client c ON c.client_id = f.client_id
LEFT JOIN core.dim_tt  dt ON dt.tt_id  = f.tt_id
JOIN core.dim_sku      s  ON s.sku_id  = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id;

-- Текущие остатки = строки ПОСЛЕДНЕГО СНИМКА клиента (НЕ последний по каждой ТТ×SKU!).
-- ВАЖНО: раньше был DISTINCT ON (client,tt,sku) — тянул старые значения выпавших из отчёта точек вперёд
-- и завышал «текущий сток» (НеоФарм 9.3млн вместо 7.1млн). Теперь берём только фактический последний снимок.
CREATE OR REPLACE VIEW marts.v_stock_latest AS
WITH last AS (
    SELECT client_id, MAX(snapshot_date) AS d FROM core.fact_stock GROUP BY 1
)
SELECT
    f.snapshot_date,
    c.name AS client, COALESCE(dt.name, dt.client_tt_code) AS tt, s.name AS sku, s.livs_article,
    CEIL(f.qty)::numeric(16,3) AS qty, f.rub_est,   -- остатки округляем ВВЕРХ
    COALESCE(p.name, s.name) AS product
FROM core.fact_stock f
JOIN last l ON l.client_id = f.client_id AND l.d = f.snapshot_date
JOIN core.dim_client c ON c.client_id = f.client_id
LEFT JOIN core.dim_tt  dt ON dt.tt_id  = f.tt_id
JOIN core.dim_sku      s  ON s.sku_id  = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id;

-- Сводка по клиенту и месяцу: закупки vs продажи (зад. 4/6)
CREATE OR REPLACE VIEW marts.v_client_month_summary AS
WITH si AS (
    SELECT client_id, period, SUM(qty) qty, SUM(rub) rub
    FROM core.fact_sellin GROUP BY client_id, period
), so AS (
    SELECT client_id, period, SUM(qty) qty, SUM(rub_est) rub
    FROM core.fact_sellout GROUP BY client_id, period
)
SELECT
    c.name AS client,
    COALESCE(si.period, so.period)              AS period,
    EXTRACT(YEAR FROM COALESCE(si.period, so.period))::int AS year,
    si.qty AS sellin_qty,  si.rub AS sellin_rub,
    so.qty AS sellout_qty, so.rub AS sellout_rub
FROM si
FULL OUTER JOIN so
    ON si.client_id = so.client_id AND si.period = so.period
JOIN core.dim_client c
    ON c.client_id = COALESCE(si.client_id, so.client_id);

-- Регистр загрузки: статус "кто сдал за месяц" (защита от частичного месяца)
CREATE OR REPLACE VIEW marts.v_load_status AS
SELECT
    c.name AS client,
    lr.period,
    lr.source,
    lr.status,
    lr.rows_loaded,
    lr.loaded_at
FROM core.load_register lr
LEFT JOIN core.dim_client c ON c.client_id = lr.client_id;

-- Закуп точки (вторичка у дистрибьютора) — для сверки с 1С Sell-In
CREATE OR REPLACE VIEW marts.v_pos_purchase AS
SELECT
    f.period,
    EXTRACT(YEAR  FROM f.period)::int            AS year,
    EXTRACT(MONTH FROM f.period)::int             AS month_num,
    EXTRACT(QUARTER FROM f.period)::int           AS quarter,
    c.client_id, c.name                           AS client,
    f.tt_id, dt.client_tt_code,
    COALESCE(dt.name, dt.client_tt_code)          AS tt,
    dt.chain_name, dt.city,
    s.sku_id, s.livs_article, s.name              AS sku,
    COALESCE(p.name, s.name)                      AS product,
    CEIL(f.qty)::numeric(16,3)                    AS qty,   -- закуп округляем ВВЕРХ до целых упаковок
    f.rub
FROM core.fact_pos_purchase f
JOIN core.dim_client c ON c.client_id = f.client_id
LEFT JOIN core.dim_tt  dt ON dt.tt_id  = f.tt_id
JOIN core.dim_sku      s  ON s.sku_id  = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id;
