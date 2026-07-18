# LIVS BI — Фаза 1

Замена PowerBI. Стек: **Postgres** (данные) + **Metabase** (дашборды) + **Python** (переходники/загрузка).
Полный дизайн — в [../LIVS_BI_design.md](../LIVS_BI_design.md).

## Что уже есть в каркасе (Фаза 1)
- `docker-compose.yml` — Postgres + Metabase + сервис приложения (Python 3.11).
- `db/01_schema.sql` — схема данных (слои `staging` / `core`), справочники, факты, служебные таблицы.
- `db/02_marts.sql` — витрины (views) под дашборды задач 3/4/6.
- `app/` — движок **переходников** (config-driven), резолвинг справочников, загрузчик, CLI `ingest`.
- `app/adapters/configs/example_client.yaml` — пример конфига переходника (под реальный файл клиента правится 1 раз).
- `sample_data/` — синтетический пример, чтобы прогнать пайплайн без реальных данных.

## Предпосылки
Установить **Docker Desktop** (Windows). Локальный Python 3.6 не используется — приложение работает в контейнере.

## Запуск
```powershell
cd d:\ToLivs\livs-bi
copy .env.example .env          # при желании поменяй пароль
docker compose up -d            # поднимет Postgres + Metabase + app
```
- Схема БД применяется автоматически при первом старте Postgres (скрипты из `db/`).
- **Metabase**: http://localhost:3000 → создать админа → подключить источник:
  Postgres, host `db`, port `5432`, db `livs_bi`, user/pароль из `.env`.

## Прогон пайплайна на синтетике
Демонстрирует реальный рабочий цикл: новые коды товаров уходят в очередь, человек
подтверждает их один раз, повторная загрузка кладёт данные в core.

```powershell
# 1) первая загрузка — товары ещё не сопоставлены, уходят в очередь
docker compose exec app python -m app.ingest load --config app/adapters/configs/example_client.yaml --file sample_data/sellout_example.csv

# 2) посмотреть очередь сопоставлений
docker compose exec app python -m app.ingest queue

# 3) подтвердить сопоставления (код клиента -> наш артикул) — один раз
docker compose exec app python -m app.ingest confirm-sku --client "Аптека Пример" --code CL-100 --article LIVS-VITC --name "ЛИВС Витамин С"
docker compose exec app python -m app.ingest confirm-sku --client "Аптека Пример" --code CL-205 --article LIVS-MGB6 --name "ЛИВС Магний B6"

# 4) повторная загрузка — строки попадают в core (ТТ создаются автоматически)
docker compose exec app python -m app.ingest load --config app/adapters/configs/example_client.yaml --file sample_data/sellout_example.csv
```
После шага 4 в Metabase появятся данные во вьюхах `marts.*` (например `marts.v_sellout`).

## Реальные данные (вход в продакшен Фазы 1)
1. Положить 2–3 клиентских отчёта + выгрузку 1С → сделаем под них конфиги переходников.
2. Залить исторический архив тем же механизмом (для YoY/YTD).
3. Собрать дашборды задач 3/4/6 в Metabase.

## Структура
```
livs-bi/
├─ docker-compose.yml      инфраструктура
├─ Dockerfile             образ приложения
├─ requirements.txt
├─ .env.example
├─ db/
│  ├─ 01_schema.sql       таблицы (staging, core)
│  └─ 02_marts.sql        витрины (views)
├─ app/
│  ├─ config.py           подключение к БД
│  ├─ canonical.py        каноническая строка + нормализация
│  ├─ mapping.py          резолвинг SKU/ТТ + очередь сопоставлений
│  ├─ loader.py           запись в staging/core + регистр загрузки
│  ├─ ingest.py           CLI-оркестратор
│  └─ adapters/
│     ├─ base.py          движок переходника (по YAML-конфигу)
│     └─ configs/
│        └─ example_client.yaml
└─ sample_data/
   └─ sellout_example.csv
```
