-- Доходность клиента (зад.10). Данные из «Sales Retail» (свод доходность + свод инвестиции).
-- Формула руководителя: Коммерческая прибыль = Sell-In − Себест − Бюджет;  Доходность% = КП / (Sell-In − Бюджет).
-- Здесь храним посчитанную руководителем доходность% (учитывает Себест ~250 ₽/шт) + компоненты (SI, Бюджет).
-- Комм.прибыль ₽ выводим: Доходность% × (SI − Бюджет).
CREATE TABLE IF NOT EXISTS core.fact_client_econ (
    id                 BIGSERIAL PRIMARY KEY,
    client             TEXT NOT NULL,
    manager            TEXT,
    channel            TEXT,
    si_2025            NUMERIC(16,2),      -- Sell-In 2025 факт, ₽
    si_2026_plan       NUMERIC(16,2),      -- Sell-In 2026 план, ₽
    share_si           NUMERIC(8,5),       -- доля в общем Sell-In
    premia             NUMERIC(16,2),
    promo              NUMERIC(16,2),
    paid_services      NUMERIC(16,2),
    certificates       NUMERIC(16,2),
    samples            NUMERIC(16,2),
    isg                NUMERIC(16,2),      -- компенсация истекающих сроков годности
    invest_total       NUMERIC(16,2),      -- Бюджет итого
    dohodnost_plan     NUMERIC(8,5),       -- доходность 2026 план (доля)
    dohodnost_forecast NUMERIC(8,5),       -- доходность 2026 прогноз (доля)
    source_file        TEXT,
    loaded_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client, source_file)
);

CREATE OR REPLACE VIEW marts.v_dohodnost AS
SELECT
    client                                       AS "Клиент",
    manager                                      AS "КАМ",
    channel                                      AS "Канал",
    ROUND(dohodnost_plan * 100, 1)               AS "Доходность план, %",
    ROUND(dohodnost_forecast * 100, 1)           AS "Доходность прогноз, %",
    ROUND(share_si * 100, 2)                      AS "Доля в SI, %",
    ROUND(si_2026_plan)                          AS "Sell-In 2026 план, руб",
    ROUND(invest_total)                          AS "Инвестиции (Бюджет), руб",
    ROUND(dohodnost_plan * (si_2026_plan - COALESCE(invest_total, 0))) AS "Комм. прибыль план, руб",
    ROUND(premia)        AS "Премия",
    ROUND(promo)         AS "Промо",
    ROUND(paid_services) AS "Платные услуги",
    ROUND(certificates)  AS "Сертификаты",
    ROUND(samples)       AS "Сэмплы",
    ROUND(isg)           AS "Компенсация ИСГ"
FROM core.fact_client_econ
WHERE client NOT LIKE 'ИТОГО%';
