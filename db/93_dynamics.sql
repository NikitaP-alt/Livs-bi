-- Динамика: продажи (Sell-Out) и закупки (Sell-In) в одном грейне сеть×товар×месяц.
-- Прирост (MoM/QoQ/YoY/YtD) считается в карточках через оконные функции.
-- Сеть = group_name (сшивает Sell-Out по имени сети и Sell-In по юрлицу 1С).
CREATE OR REPLACE VIEW marts.v_dynamics AS
WITH so AS (
    SELECT dc.group_name AS grp, COALESCE(p.name, s.name) AS product, f.period AS period,
           SUM(f.qty) AS so_qty
    FROM core.fact_sellout f
    JOIN core.dim_client  dc ON dc.client_id = f.client_id
    JOIN core.dim_sku     s  ON s.sku_id     = f.sku_id
    LEFT JOIN core.dim_product p ON p.product_id = s.product_id
    GROUP BY 1, 2, 3
), si AS (
    SELECT dc.group_name AS grp, COALESCE(p.name, s.name) AS product, f.period AS period,
           SUM(f.qty) AS si_qty, SUM(f.rub) AS si_rub
    FROM core.fact_sellin f
    JOIN core.dim_client  dc ON dc.client_id = f.client_id
    JOIN core.dim_sku     s  ON s.sku_id     = f.sku_id
    LEFT JOIN core.dim_product p ON p.product_id = s.product_id
    GROUP BY 1, 2, 3
)
SELECT
    COALESCE(so.grp, si.grp)                         AS "Сеть/группа",
    COALESCE(so.product, si.product)                 AS "Товар",
    COALESCE(so.period, si.period)                   AS "Период",
    EXTRACT(YEAR FROM COALESCE(so.period, si.period))::int AS "Год",
    so.so_qty                                        AS "Продажи, шт",
    si.si_qty                                        AS "Закупки, шт",
    si.si_rub                                        AS "Закупки, руб"
FROM so
FULL JOIN si ON so.grp = si.grp AND so.product = si.product AND so.period = si.period;
