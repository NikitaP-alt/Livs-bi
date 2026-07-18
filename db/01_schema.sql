-- ============================================================
-- LIVS BI — схема данных (Фаза 1)
-- Слои: staging (сырьё как пришло) -> core (справочники + факты)
-- Грейн фактов продаж = месяц (period = первое число месяца).
-- ============================================================

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;

-- ------------------------------------------------------------
-- STAGING: сырые строки каждой загрузки (для аудита и переразбора)
-- ------------------------------------------------------------
CREATE TABLE staging.raw_upload (
    id          BIGSERIAL PRIMARY KEY,
    client_name TEXT,
    source      TEXT NOT NULL,           -- sellout | stock | sellin | matrix | plan | economics
    file_name   TEXT,
    period      DATE,                     -- отчётный месяц (1-е число)
    payload     JSONB NOT NULL,           -- строка файла как есть
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------
-- CORE: справочники
-- ------------------------------------------------------------

-- Клиент = бизнес-клиент (может объединять несколько ИНН)
CREATE TABLE core.dim_client (
    client_id   SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    group_name  TEXT,                    -- сеть/группа (для сверки Sell-In↔Sell-Out); ведёт app/build_groups.py
    channel_type TEXT,                   -- канал: Аптечная сеть/Дистрибьютор/Маркетплейс/Ритейл/Онлайн-аптека/СНГ
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ИНН -> клиент (много ИНН на одного клиента)
CREATE TABLE core.client_inn (
    inn         TEXT PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id)
);

-- Торговая точка (под клиентом). Опознаётся кодом точки клиента.
CREATE TABLE core.dim_tt (
    tt_id           SERIAL PRIMARY KEY,
    client_id       INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    client_tt_code  TEXT NOT NULL,        -- ключ точки внутри клиента (код или нормализованный адрес)
    name            TEXT,
    address         TEXT,
    inn             TEXT,                  -- ИНН юрлица точки
    chain_name      TEXT,                  -- аптечная сеть/юрлицо (атрибут для дрилл-дауна)
    city            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, client_tt_code)
);

-- Мастер-товар (канонический товар ЛИВС); наполняет классификатор app/build_master.py
CREATE TABLE core.dim_product (
    product_id  SERIAL PRIMARY KEY,
    code        TEXT UNIQUE,            -- ключ классификатора (напр. D3_2000)
    name        TEXT NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE   -- FALSE = снят с продажи (остаётся в истории)
);

-- SKU (провизорный товар, как в отчёте клиента); привязывается к мастер-товару
CREATE TABLE core.dim_sku (
    sku_id        SERIAL PRIMARY KEY,
    livs_article  TEXT UNIQUE,            -- наш артикул
    name          TEXT NOT NULL,
    barcode       TEXT,
    product_id    INTEGER REFERENCES core.dim_product(product_id)   -- мастер-товар (build_master.py)
);

-- Кросс-таблица: код товара клиента -> наш артикул (ведётся на клиента)
CREATE TABLE core.map_client_sku (
    client_id        INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    client_sku_code  TEXT NOT NULL,
    sku_id           INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    PRIMARY KEY (client_id, client_sku_code)
);

-- Прайс клиента (для оценки Sell-Out/остатков в рублях). Источник — 1С.
CREATE TABLE core.dim_price (
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    sku_id      INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    period      DATE NOT NULL,
    price_rub   NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (client_id, sku_id, period)
);

-- Утверждённый прайс по мастер-товару (ценовая политика LIVS). Один прайс на компанию,
-- не поклиентский. Нужен, чтобы оценить Sell-Out в рублях там, где отчёт содержит только
-- количество (Диалог, Фармаимпекс и т.п.). Наполняет app/load_price_policy.py.
CREATE TABLE core.dim_product_price (
    product_id  INTEGER PRIMARY KEY REFERENCES core.dim_product(product_id),
    ext_id      TEXT,            -- ID из ценовой политики (6835xxx)
    ext_name    TEXT,            -- наименование из прайса (англ.)
    price_vat   NUMERIC(14,2),   -- Цена с НДС (Прайс Базовый ПП) = закупка = Sell-In
    rrc         NUMERIC(14,2),   -- РРЦ (рекоменд. розничная цена)
    approx      BOOLEAN DEFAULT FALSE,   -- TRUE = прайс-прокси (нет точной строки в политике)
    updated     DATE DEFAULT CURRENT_DATE
);

-- Контрактная матрица (зад. 8) — заготовка для Фазы 2
CREATE TABLE core.dim_matrix (
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    sku_id      INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    valid_from  DATE NOT NULL,
    valid_to    DATE,
    PRIMARY KEY (client_id, sku_id, valid_from)
);

-- План (зад. 9) — заготовка для Фазы 2
CREATE TABLE core.dim_plan (
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    sku_id      INTEGER REFERENCES core.dim_sku(sku_id),   -- NULL = план на уровне клиента
    period      DATE NOT NULL,
    plan_qty    NUMERIC(16,3),
    plan_rub    NUMERIC(16,2)
);

-- Экономика (зад. 10) — заготовка для Фазы 3
CREATE TABLE core.dim_economics (
    sku_id      INTEGER REFERENCES core.dim_sku(sku_id),
    client_id   INTEGER REFERENCES core.dim_client(client_id),
    period      DATE NOT NULL,
    cost_rub    NUMERIC(14,2),     -- себестоимость за ед.
    invest_rub  NUMERIC(16,2)      -- инвестиции за период
);

-- ------------------------------------------------------------
-- CORE: факты
-- ------------------------------------------------------------

-- Sell-In = отгрузки ЛИВС клиенту (закупки клиента), уровень клиента
CREATE TABLE core.fact_sellin (
    id          BIGSERIAL PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    sku_id      INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    period      DATE NOT NULL,
    qty         NUMERIC(16,3) NOT NULL,
    rub         NUMERIC(16,2),          -- выручка (без НДС, как в 1С)
    cost_rub    NUMERIC(16,2),          -- себестоимость за период (из 1С); прибыль = rub - cost_rub
    source_file TEXT,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (client_id, sku_id, period, source_file)
);

-- Sell-Out = продажа из точки конечному покупателю, уровень ТТ
CREATE TABLE core.fact_sellout (
    id          BIGSERIAL PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    tt_id       INTEGER REFERENCES core.dim_tt(tt_id),
    sku_id      INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    period      DATE NOT NULL,
    qty         NUMERIC(16,3) NOT NULL,
    rub_est     NUMERIC(16,2),     -- оценка в рублях через прайс клиента
    source_file TEXT,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Остатки = снимок на дату, уровень ТТ
CREATE TABLE core.fact_stock (
    id            BIGSERIAL PRIMARY KEY,
    client_id     INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    tt_id         INTEGER REFERENCES core.dim_tt(tt_id),
    sku_id        INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    snapshot_date DATE NOT NULL,
    qty           NUMERIC(16,3) NOT NULL,
    rub_est       NUMERIC(16,2),
    source_file   TEXT,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Закуп точки = вторичная закупка точки у дистрибьютора (НЕ отгрузки ЛИВС).
-- Сверяется позже с Sell-In из 1С. Уровень ТТ, есть рубли.
CREATE TABLE core.fact_pos_purchase (
    id          BIGSERIAL PRIMARY KEY,
    client_id   INTEGER NOT NULL REFERENCES core.dim_client(client_id),
    tt_id       INTEGER REFERENCES core.dim_tt(tt_id),
    sku_id      INTEGER NOT NULL REFERENCES core.dim_sku(sku_id),
    period      DATE NOT NULL,
    qty         NUMERIC(16,3) NOT NULL,
    rub         NUMERIC(16,2),
    source_file TEXT,
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Рыночные цены площадок (парсер). Отдельная метрика — ценовой мониторинг.
CREATE TABLE core.fact_price_market (
    id          BIGSERIAL PRIMARY KEY,
    sku_id      INTEGER REFERENCES core.dim_sku(sku_id),
    marketplace TEXT NOT NULL,     -- wb | ozon | apteka_ru | eapteka
    week        DATE NOT NULL,     -- понедельник недели
    price_rub   NUMERIC(14,2)
);

-- ------------------------------------------------------------
-- CORE: служебные
-- ------------------------------------------------------------

-- Регистр загрузки: кто и за какой месяц сдал (защита от "частичного месяца")
CREATE TABLE core.load_register (
    id           BIGSERIAL PRIMARY KEY,
    client_id    INTEGER REFERENCES core.dim_client(client_id),
    period       DATE NOT NULL,
    source       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'loaded',  -- loaded | partial | error
    file_name    TEXT,
    rows_loaded  INTEGER,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Очередь сопоставлений: новые коды товаров/точек, ещё не привязанные
CREATE TABLE core.mapping_queue (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,          -- sku | tt
    client_id     INTEGER REFERENCES core.dim_client(client_id),
    raw_code      TEXT NOT NULL,
    raw_name      TEXT,
    suggested_id  INTEGER,                -- предложение ИИ/похожести (sku_id или tt_id)
    status        TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | rejected
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (kind, client_id, raw_code)
);

-- Индексы под типовые срезы
CREATE INDEX ix_sellin_period   ON core.fact_sellin (period);
CREATE INDEX ix_sellout_period  ON core.fact_sellout (period);
CREATE INDEX ix_sellout_client  ON core.fact_sellout (client_id);
CREATE INDEX ix_stock_date      ON core.fact_stock (snapshot_date);
