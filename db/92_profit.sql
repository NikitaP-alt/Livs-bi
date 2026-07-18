-- Доходность/рентабельность по Sell-In (данные 1С): выручка, себестоимость, прибыль.
-- Рентабельность% считается в карточках как SUM(прибыль)/SUM(выручка) (построчно усреднять нельзя).
CREATE OR REPLACE VIEW marts.v_profit AS
SELECT
  dc.group_name                       AS "Сеть/группа",
  f.period                            AS "Период",
  EXTRACT(YEAR FROM f.period)::int     AS "Год",
  s.name                              AS "Товар",
  f.qty                               AS "Кол-во",
  f.rub                               AS "Выручка, руб",
  f.cost_rub                          AS "Себест., руб",
  (f.rub - f.cost_rub)                AS "Прибыль, руб"
FROM core.fact_sellin f
JOIN core.dim_client dc ON dc.client_id = f.client_id
JOIN core.dim_sku    s  ON s.sku_id     = f.sku_id
WHERE f.rub IS NOT NULL;
