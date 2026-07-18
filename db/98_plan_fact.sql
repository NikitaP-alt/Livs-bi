-- План-факт (зад.9). Из «ПЛАН ФАКТ 2026» (её собственный план-факт, самосогласованный).
-- Грейн: Клиент × Канал(Ритейл/E-com) × Показатель × Период(квартал/год). План + Факт/Прогноз.
-- Q1=факт (закрыт), Q2-4=прогноз (КАМы обновляют). Выполнение% = Факт/План.
CREATE TABLE IF NOT EXISTS core.fact_plan_fact (
    id           BIGSERIAL PRIMARY KEY,
    client       TEXT NOT NULL,
    channel      TEXT,                    -- Ритейл | E-com
    metric       TEXT NOT NULL,           -- Sell In, шт | Sell In, руб | Sell Out, шт | Sell Out, руб
    period_label TEXT NOT NULL,           -- 1Q26..4Q26 | 2026 | 2025
    quarter      INT,                     -- 1..4, NULL для года
    plan         NUMERIC(18,2),
    fact         NUMERIC(18,2),           -- факт (Q1) или прогноз (Q2-4/год)
    source_file  TEXT,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client, channel, metric, period_label, source_file)
);

CREATE OR REPLACE VIEW marts.v_plan_fact AS
SELECT
    client                                       AS "Клиент",
    channel                                      AS "Канал",
    metric                                       AS "Показатель",
    period_label                                 AS "Период",
    quarter                                      AS "Квартал №",
    ROUND(plan)                                  AS "План",
    ROUND(fact)                                  AS "Факт/Прогноз",
    ROUND(100.0 * fact / NULLIF(plan, 0), 1)     AS "Выполнение, %"
FROM core.fact_plan_fact;
