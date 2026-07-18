-- Матрица: соблюдение ассортимента (зад.8). ВЫЧИСЛЯЕМАЯ из остатков (Вариант B) — обновляется сама.
-- Соблюдение = ТТ со стоком товара / все активные ТТ сети в этом снимке.
-- Считается по МАСТЕР-товару (дубли SKU схлопываются). Пока осмысленно там, где остатки поточечные (Диалог и т.п.).
-- Прим.: «авторизовано» ~ все активные ТТ месяца (для Диалога = 88, как в файле руководителя). Реальные матрицы
-- (какие SKU где положены) подставим, когда руководитель их даст.
DROP VIEW IF EXISTS marts.v_matrix;
DROP TABLE IF EXISTS core.fact_matrix CASCADE;

CREATE VIEW marts.v_matrix AS
WITH auth AS (   -- активные ТТ сети в снимке = знаменатель
    SELECT f.client_id, f.snapshot_date, COUNT(DISTINCT f.tt_id) AS authorized_tt
    FROM core.fact_stock f
    WHERE f.qty > 0 AND f.tt_id IS NOT NULL
    GROUP BY 1, 2
), prod AS (     -- ТТ со стоком по мастер-товару
    SELECT f.client_id, f.snapshot_date, COALESCE(p.name, s.name) AS product,
           COUNT(DISTINCT f.tt_id) AS tt_stocked, SUM(f.qty) AS stock_units
    FROM core.fact_stock f
    JOIN core.dim_sku s ON s.sku_id = f.sku_id
    LEFT JOIN core.dim_product p ON p.product_id = s.product_id
    WHERE f.qty > 0 AND f.tt_id IS NOT NULL
    GROUP BY 1, 2, 3
)
SELECT
    c.name                                              AS "Сеть/группа",
    pr.product                                          AS "Товар",
    pr.snapshot_date                                    AS "Период",
    EXTRACT(YEAR FROM pr.snapshot_date)::int             AS "Год",
    a.authorized_tt                                     AS "Авторизовано ТТ",
    pr.tt_stocked                                       AS "ТТ со стоком",
    CEIL(pr.stock_units)::numeric(16,3)                 AS "Сток, шт",
    ROUND(100.0 * pr.tt_stocked / NULLIF(a.authorized_tt, 0), 1) AS "Соблюдение, %"
FROM prod pr
JOIN auth a ON a.client_id = pr.client_id AND a.snapshot_date = pr.snapshot_date
JOIN core.dim_client c ON c.client_id = pr.client_id;
