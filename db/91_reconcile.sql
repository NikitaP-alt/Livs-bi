-- Сверка Sell-In (отгрузки ЛИВС из 1С) vs Sell-Out (продажи сетей) по группе×месяцу.
CREATE OR REPLACE VIEW marts.v_reconcile AS
WITH si AS (
  SELECT dc.group_name AS g, f.period AS p, SUM(f.qty)::numeric AS q, SUM(f.rub)::numeric AS r
  FROM core.fact_sellin f
  JOIN core.dim_client dc ON dc.client_id = f.client_id
  WHERE dc.group_name IS NOT NULL
  GROUP BY 1, 2
), so AS (
  SELECT dc.group_name AS g, f.period AS p, SUM(f.qty)::numeric AS q
  FROM core.fact_sellout f
  JOIN core.dim_client dc ON dc.client_id = f.client_id
  WHERE dc.group_name IS NOT NULL
  GROUP BY 1, 2
)
SELECT
  COALESCE(si.g, so.g)                              AS "Сеть/группа",
  COALESCE(si.p, so.p)                              AS "Период",
  EXTRACT(YEAR FROM COALESCE(si.p, so.p))::int      AS "Год",
  si.q                                             AS "Sell-In, шт",
  si.r                                             AS "Sell-In, руб",
  so.q                                             AS "Sell-Out, шт",
  (so.q / NULLIF(si.q, 0))                          AS "Sell-Out / Sell-In"
FROM si
FULL JOIN so ON si.g = so.g AND si.p = so.p;
