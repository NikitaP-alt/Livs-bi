-- План-факт ПОМЕСЯЧНО (зад.9, помесячный слой). Источник: Sales Retail «SI-SO-ST»
-- (помесячный план/факт/форкаст по сетям). Грейн факта: Канал × Сеть × КАМ × Показатель × Год × Тип × Месяц.
-- Тип: план (цель) | факт (закрытые месяцы) | форкаст (живой прогноз КАМов). Наполняет app/load_plan_month.py.
CREATE TABLE IF NOT EXISTS core.fact_plan_month (
    id           BIGSERIAL PRIMARY KEY,
    channel      TEXT,
    client       TEXT NOT NULL,           -- Сеть
    kam          TEXT,
    metric       TEXT NOT NULL,           -- Sell In, шт|руб · Sell Out, шт|руб · Stock, шт|руб|мес|ср-е
    year         INT  NOT NULL,
    kind         TEXT NOT NULL,           -- план | факт | форкаст
    month_num    INT  NOT NULL,           -- 1..12
    value        NUMERIC(18,2),
    source_file  TEXT,
    UNIQUE (channel, client, metric, year, kind, month_num, source_file)
);

-- Пивот план/факт/прогноз по клиенту × показателю × году × месяцу + выполнение %.
CREATE OR REPLACE VIEW marts.v_plan_fact_month AS
SELECT
    client, metric, year, month_num,
    (ARRAY['Янв','Фев','Мар','Апр','Май','Июн','Июл','Авг','Сен','Окт','Ноя','Дек'])[month_num] AS month,
    SUM(value) FILTER (WHERE kind = 'план')    AS plan,
    SUM(value) FILTER (WHERE kind = 'факт')     AS fact,
    SUM(value) FILTER (WHERE kind = 'форкаст')  AS forecast,
    -- «живое» ожидание: факт по закрытым месяцам, прогноз по будущим (модель руководителя)
    COALESCE(SUM(value) FILTER (WHERE kind = 'факт'),
             SUM(value) FILTER (WHERE kind = 'форкаст')) AS expected
FROM core.fact_plan_month
GROUP BY client, metric, year, month_num;
