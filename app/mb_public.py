"""Включить публичный доступ к дашбордам Metabase + выдать публичные ссылки (без логина).

Публичные UUID стабильны и не зависят от URL туннеля.
Запуск: docker compose exec -T app python -m app.mb_public
"""
from . import mb

DASHBOARDS = [
    (100, "Клиент — разбор"),
    (69, "Доходность (Комм. прибыль)"),
    (70, "План-факт"),
    (71, "Прогноз"),
    (68, "Матрица — соблюдение"),
    (36, "Динамика и прирост"),
    (5, "Сверка Sell-In / Sell-Out"),
    (37, "Клиенты и каналы"),
    (38, "Остатки: покрытие"),
    (2, "Продажи и остатки"),
    (3, "Остатки и закуп"),
    (4, "Sell-In (отгрузки 1С)"),
    (6, "Валовая маржа (1С)"),
]


def main():
    s = mb.client()
    # включить публичный шеринг
    s.put(f"{mb.MB}/api/setting/enable-public-sharing", json={"value": True})
    print("публичный доступ включён\n")

    print("=== ПУБЛИЧНЫЕ ССЫЛКИ (путь; базу-домен подставит туннель) ===")
    for did, name in DASHBOARDS:
        r = s.post(f"{mb.MB}/api/dashboard/{did}/public_link")
        try:
            uuid = r.json().get("uuid")
        except Exception:
            uuid = None
        if not uuid:  # уже расшарен -> прочитать существующий
            uuid = s.get(f"{mb.MB}/api/dashboard/{did}").json().get("public_uuid")
        print(f"  {name:<30} /public/dashboard/{uuid}")


if __name__ == "__main__":
    main()
