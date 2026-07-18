-- Прогноз продаж/закупок (зад.7). Метод: run-rate (средний уровень 12 мес) × сезонный индекс месяца.
-- Наполняет app/build_forecast.py. kind: 'факт' (история) | 'прогноз' (будущее).
CREATE TABLE IF NOT EXISTS core.fact_forecast (
    id      BIGSERIAL PRIMARY KEY,
    metric  TEXT NOT NULL,          -- Продажи | Закупки
    scope   TEXT NOT NULL,          -- ИТОГО | <сеть/группа>
    period  DATE NOT NULL,
    value   NUMERIC(18,3),
    kind    TEXT NOT NULL,          -- факт | прогноз
    UNIQUE (metric, scope, period)
);

CREATE OR REPLACE VIEW marts.v_forecast AS
SELECT
    scope                            AS "Сеть/группа",
    metric                           AS "Метрика",
    period                           AS "Период",
    EXTRACT(YEAR FROM period)::int    AS "Год",
    ROUND(value)                     AS "Значение, шт",
    kind                             AS "Тип"
FROM core.fact_forecast;
