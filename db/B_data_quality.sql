-- Контроль качества данных: помесячные итоги по сети×метрике + изменение месяц-к-месяцу.
-- Ловит «резкие скачки» (как баг стока: сток раздулся 2.5x → сразу видно как +150% MoM).
CREATE OR REPLACE VIEW marts.v_dq_monthly AS
WITH m AS (
    SELECT 'Продажи'::text metric, dc.group_name grp, date_trunc('month', f.period)::date per, SUM(f.qty) qty
    FROM core.fact_sellout f JOIN core.dim_client dc ON dc.client_id=f.client_id
    WHERE dc.group_name IS NOT NULL GROUP BY 2, 3
  UNION ALL
    SELECT 'Закуп', dc.group_name, date_trunc('month', f.period)::date, SUM(f.qty)
    FROM core.fact_pos_purchase f JOIN core.dim_client dc ON dc.client_id=f.client_id
    WHERE dc.group_name IS NOT NULL GROUP BY 2, 3
  UNION ALL
    SELECT 'Sell-In', dc.group_name, date_trunc('month', f.period)::date, SUM(f.qty)
    FROM core.fact_sellin f JOIN core.dim_client dc ON dc.client_id=f.client_id
    WHERE dc.group_name IS NOT NULL GROUP BY 2, 3
  UNION ALL
    SELECT 'Остатки', dc.group_name, date_trunc('month', f.snapshot_date)::date, SUM(f.qty)
    FROM core.fact_stock f JOIN core.dim_client dc ON dc.client_id=f.client_id
    WHERE dc.group_name IS NOT NULL GROUP BY 2, 3
)
SELECT metric AS "Метрика", grp AS "Сеть/группа", per AS "Период", qty AS "Значение",
       LAG(qty) OVER w AS "Пред. месяц",
       ROUND(100.0 * (qty - LAG(qty) OVER w) / NULLIF(LAG(qty) OVER w, 0), 0) AS "Изменение, %"
FROM m WINDOW w AS (PARTITION BY metric, grp ORDER BY per);
