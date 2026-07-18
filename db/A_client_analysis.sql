-- «Клиент — разбор» (правки руководителя #1-3,6): Sell-In + Sell-Out в одной витрине с переключением фильтром.
-- Sell-Out поточечный (есть tt_id), Sell-In из 1С клиентский (tt_id=NULL) -> кол-во ТТ только по Sell-Out.
CREATE OR REPLACE VIEW marts.v_client_analysis AS
SELECT 'Sell-Out'::text AS "Метрика", dc.group_name AS "Клиент",
       COALESCE(p.name, s.name) AS "Товар", f.period AS "Период",
       EXTRACT(YEAR FROM f.period)::int AS "Год", f.tt_id AS tt_id,
       f.qty AS qty, COALESCE(f.rub_est, ROUND(f.qty * pp.price_vat, 2))::numeric(16,2) AS rub
FROM core.fact_sellout f
JOIN core.dim_client dc ON dc.client_id = f.client_id
JOIN core.dim_sku    s  ON s.sku_id     = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id
LEFT JOIN core.dim_product_price pp ON pp.product_id = s.product_id
WHERE dc.group_name IS NOT NULL
UNION ALL
SELECT 'Sell-In', dc.group_name, COALESCE(p.name, s.name), f.period,
       EXTRACT(YEAR FROM f.period)::int, NULL::int, f.qty, f.rub
FROM core.fact_sellin f
JOIN core.dim_client dc ON dc.client_id = f.client_id
JOIN core.dim_sku    s  ON s.sku_id     = f.sku_id
LEFT JOIN core.dim_product p ON p.product_id = s.product_id
WHERE dc.group_name IS NOT NULL;
