-- Покрытие склада: на сколько хватит остатка при текущем темпе продаж.
-- Остаток = последний снимок по клиент×ТТ×SKU; темп = средние продажи в мес за последние 3 месяца.
-- Грейн: сеть×товар (можно раскрыть по каждому товару/SKU). «Хватит на, мес» = остаток / темп.
CREATE OR REPLACE VIEW marts.v_stock_coverage AS
WITH lastsnap AS (   -- последний снимок КЛИЕНТА (не по каждой ТТ×SKU — иначе тянет старое вперёд)
    SELECT client_id, MAX(snapshot_date) AS d FROM core.fact_stock GROUP BY 1
), latest AS (
    SELECT f.client_id, f.sku_id, f.qty
    FROM core.fact_stock f
    JOIN lastsnap ls ON ls.client_id = f.client_id AND ls.d = f.snapshot_date
), stock AS (
    SELECT dc.group_name g, COALESCE(p.name, s.name) product, SUM(CEIL(l.qty)) stock_qty
    FROM latest l
    JOIN core.dim_client dc ON dc.client_id = l.client_id
    JOIN core.dim_sku    s  ON s.sku_id     = l.sku_id
    LEFT JOIN core.dim_product p ON p.product_id = s.product_id
    GROUP BY 1, 2
), recent AS (
    SELECT dc.group_name g, COALESCE(p.name, s.name) product, SUM(f.qty) / 3.0 avg_month
    FROM core.fact_sellout f
    JOIN core.dim_client dc ON dc.client_id = f.client_id
    JOIN core.dim_sku    s  ON s.sku_id     = f.sku_id
    LEFT JOIN core.dim_product p ON p.product_id = s.product_id
    WHERE f.period > (SELECT MAX(period) FROM core.fact_sellout) - INTERVAL '3 months'
    GROUP BY 1, 2
)
SELECT
    COALESCE(st.g, r.g)                            AS "Сеть/группа",
    COALESCE(st.product, r.product)                AS "Товар",
    COALESCE(st.stock_qty, 0)                      AS "Остаток, шт",
    ROUND(COALESCE(r.avg_month, 0)::numeric, 1)    AS "Продажи в мес (ср. 3м), шт",
    ROUND((st.stock_qty / NULLIF(r.avg_month, 0))::numeric, 1) AS "Хватит на, мес"
FROM stock st
FULL JOIN recent r ON st.g = r.g AND st.product = r.product;
