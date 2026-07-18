# AI_ARCHITECTURE — Архитектура и правила проекта LIVS BI

> Читать в начале каждой задачи и когда «троишь»/путаешься в зависимостях.

## Цель проекта
Замена PowerBI: загрузить корпус отчётов аптечных сетей (37 клиентов, ~1162 файла, 2022–2026)
в Postgres и показывать аналитику в Metabase (русский интерфейс, светлая тема).
Периметр — ТГ-список из 10 задач (НЕ по старым письмам). Полный дизайн: `../LIVS_BI_design.md`,
план ETL: `../LIVS_ETL_plan.md`.

## Стек
- **Python 3.11** в Docker (локальный системный Python 3.6 НЕ использовать).
- **PostgreSQL 16** — хранилище. **Metabase** — дашборды. **Docker Compose** — оркестрация.
- Библиотеки: pandas, openpyxl, **xlrd>=2.0.1** (.xls), SQLAlchemy 2.0, psycopg2-binary, PyYAML, python-dotenv, streamlit.
- Запуск локально на ПК пользователя (Windows). Прод позже — RF VM (152-ФЗ: ПДн только в РФ!).

## Структура проекта (`livs-bi/`)
```
docker-compose.yml (+ том metabase-data: дашборды персистентны) / docker-compose.prod.yml / Dockerfile / .env
db/   00_create_metabase_db.sql, 01_schema.sql (staging+core, +group_name/channel_type/cost_rub/dim_product),
      02_marts.sql (базовые вьюхи; v_sellout.city=COALESCE→'(город не определён)'), 90_city_geo.sql (карта),
      91_reconcile.sql (сверка), 92_profit.sql (валовая маржа 1С), 93_dynamics.sql (динамика), 94_channels.sql (каналы),
      95_coverage.sql (покрытие), 96_matrix.sql (матрица, вычисляемая), 97_dohodnost.sql (доходность+инвестиции),
      98_plan_fact.sql (план-факт), 99_forecast.sql (прогноз)
app/
  config.py        — движок БД (DATABASE_URL)
  canonical.py     — SalesRow (каноническая строка)
  loader.py        — запись staging/core, delete_prior (идемпотентность), load_register
  mapping.py       — резолвинг: get_or_create_client/tt, resolve/auto_create_sku
  ingest.py        — CLI одного файла (load/queue/confirm-sku) + _load_rows (ядро загрузки)
  batch.py         — БАТЧ-загрузка корпуса: вывод периода из путей (parse_period), обход дерева
  registry.py      — РЕЕСТР: папка клиента -> переходник (yaml|py) + skip-правила
  build_master.py  — классификатор мастер-товаров (dim_product), правила по названию
  load_1c.py       — загрузка выгрузки 1С (Sell-In: qty+rub+cost_rub) из сводного пивота
  build_groups.py  — справочник контрагент 1С -> сеть (group_name) + канал (channel_type)
  ui.py            — Streamlit GUI загрузки отчётов (порт 8501)
  survey.py / inspect.py — разведка форматов / осмотр одного файла
  load_dohodnost.py — доходность+инвестиции из Sales Retail (свод доходность/инвестиции)
  load_plan_fact.py — план-факт из «ПЛАН ФАКТ 2026» (Ритейл+E-com, кварталы)
  build_forecast.py — прогноз (run-rate × сезонность; SKIP_RECENT=2 неполных мес)
  enrich_city.py    — город точки из имени/адреса (словарь + «<Город> г,»)
  load_baza.py      — город из «База клиентов» (Соц.аптека префикс, Диалог норм.код)
  check_pf_1c.py    — сверка план-факт↔1С (утилита, печать)
  mb.py            — хелперы Metabase API (login, upsert карточек/дашбордов, field-filter'ы)
  mb_public.py     — публичные ссылки на 12 дашбордов (для деплоя). mb_viewer.py — view-only юзер + права.
  build_*_dashboard.py — сборка дашбордов (recon/profit/dynamics/channels/coverage/matrix/dohodnost/plan_fact/forecast;
                          нативный SQL, идемпотентно). build_all_dashboards.py — пересобрать все разом.
  fix_main_filters.py — чинит привязки фильтров MBQL-дашбордов id=2/3 к текущим полям витрин (self-heal)
  mb_maint.py      — инвентаризация + health-check всех карточек (только чтение)
  adapters/
    base.py        — YAML-движок переходника (построчные форматы; алиасы колонок, tt_compose, tt_inn/city/chain)
    configs/*.yaml — переходники простых клиентов (eapteka, apteka_ru, lekopttorg, sotsialnaya, nevis, ...)
    custom/*.py    — переходники сложных клиентов (dialog, neofarm, planeta, vita_tomsk, vita_samara, ...)
incoming/отчеты/   — исходные Excel по клиентам (НЕ в git; ПДн); incoming/1С/, incoming/план/ (файлы руководителя)
backup/livs_bi.dump (дамп БД) / metabase-data/ (H2 Metabase) / scripts/backup.sh / DEPLOY.md / MIGRATION.md
```

## Слои данных
`staging.raw_upload` (сырьё) → `core` (справочники `dim_*` + факты `fact_*` + служебные) → `marts.*` (вьюхи для Metabase).
- Справочники: dim_client (+`group_name` сеть, +`channel_type` канал), client_inn, dim_tt, dim_sku (+`product_id`),
  **dim_product** (мастер-товар) + map_client_sku.
- Факты: fact_sellout, fact_stock (снимок), fact_pos_purchase (закуп точки/вторичка),
  **fact_sellin** (1С, ЗАГРУЖЕН: qty+rub+`cost_rub`), fact_price_market (парсер).
- Грейн = месяц. Остатки = снимок на конец месяца.

## Витрины (marts) и дашборды (Metabase, коллекция «LIVS BI»)
Витрины строятся через `group_name` (сшивает Sell-Out по имени сети и Sell-In по юрлицу 1С):
- `v_sellout` / `v_stock` / `v_stock_latest` / `v_pos_purchase` / `v_sellin` — базовые (02_marts).
- `v_reconcile` — сверка Sell-In↔Sell-Out по сеть×месяц (91). `v_profit` — доходность из 1С (92).
- `v_dynamics` — продажи+закупки по сеть×товар×месяц для прироста MoM/QoQ/YoY/YtD (93).
- `v_channel_summary` — каналы + доля клиента в Sell-In (94). `v_stock_coverage` — «на сколько хватит» (95).
- `v_matrix` — соблюдение матрицы, ВЫЧИСЛЯЕМАЯ из fact_stock (96, ТТ со стоком/активные ТТ, по мастер-товару).
- `v_dohodnost` — Коммерческая прибыль (fact_client_econ, 97). `v_plan_fact` — план-факт (fact_plan_fact, 98).
- `v_forecast` — факт+прогноз (fact_forecast, 99). `v_city_sales` — карта по городам (90).
**12 дашбордов** (коллекция «LIVS BI»): id=2 Продажи · 3 Остатки/закуп · 4 Sell-In · 5 Сверка · 6 Валовая маржа(1С) ·
36 Динамика · 37 Каналы · 38 Покрытие · 68 Матрица · 69 Доходность(Комм.прибыль) · 70 План-факт · 71 Прогноз.
Дашборд-скрипты идемпотентны (карточка/дашборд по имени переиспользуются). Фильтры = field-filter'ы; где они
используются, витрину НЕ алиасить (MB подставляет полное имя таблицы). Тестировать фильтры через python/requests
(UTF-8), НЕ через PowerShell Invoke-RestMethod (шлёт кириллицу не в UTF-8 → пустой матч).

## Паттерны и соглашения
- **Переходник на клиента**: простой построчный → YAML-конфиг; сложный (мультилист/пивот/агрегация) → Python в `adapters/custom/`. Все custom: `adapt(file_path, period_override) -> (rows, raw_records)` + `CLIENT`.
- **Реестр** (`registry.py`): имя папки клиента → как грузить. `SKIP_DIR_PARTS` (База клиентов/ОСГ), `skip_files` (регэксп) на клиента.
- **Период**: `batch.parse_period(path)` выводит YYYY-MM из путей/имён (MM.YY, YYYY_MM_DD, DD.MM.YYYY, «Май 2024», месяц-в-имени+год-в-папке). Если None — период берёт сам переходник из данных.
- **Идемпотентность**: `source_file` = относительный путь файла; `delete_prior` удаляет прежнюю загрузку файла перед вставкой. Повторный запуск НЕ двоит.
- **SKU**: код/название клиента → `auto_create_sku` (провизорный, `--auto-sku`), затем `build_master.py` раскладывает в 24 мастер-товара по правилам названия. ТТ — авто-создаётся.
- **Только бренд ЛИВС**: в файлах бывают чужие бренды (Ригла=ABC) → фильтровать.
- **Агрегация**: строки по партиям/накладным → СУММА по (период, точка, товар). Остаток у некоторых = повтор на точку → НЕ суммировать (проверять!).
- **ВАЖНО — дрейф форматов**: формат меняется по годам ВНУТРИ клиента. Один конфиг часто не покрывает всю историю — нужны варианты по эрам.

## Запуск
- Поднять: Docker Desktop → `docker compose start` (после рестарта ПК Docker запускать вручную).
- Загрузка: `docker compose exec -T app python -m app.batch "<Клиент>"` (или без аргументов — все из реестра).
- Классификатор: `docker compose exec -T app python -m app.build_master`.
- Metabase: http://localhost:3000 (логин в AI_CURRENT_STATE). Источник: host `db`, db `livs_bi`.

## Среда (грабли)
- Windows PowerShell 5.1: нет `&&`; кириллица в SQL через stdin рискованна → удалять/фильтровать по ЧИСЛОВЫМ id.
- `.xls` нужен xlrd (есть). «Битый» xlsx без sharedStrings (Фармленд/Фармперспектива) — отдельный ридер.
