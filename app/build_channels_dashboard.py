"""Дашборд «Клиенты и каналы» в Metabase (нативный SQL, marts.v_channel_summary).

Списки клиентов по каналам продаж + доля клиента в Sell-In (ответ на «долю клиента», зад.5).
Фильтр: Канал. Запуск: docker compose exec -T app python -m app.build_channels_dashboard
"""
import time
from . import mb

DASH = "Клиенты и каналы"
V = "marts.v_channel_summary"
TOT = f'(SELECT SUM("Sell-In, руб") FROM {V})'  # знаменатель доли = весь Sell-In (без фильтра)

CARDS = [
    ("Сетей/групп (в фильтре)", "scalar",
     f'SELECT COUNT(*) FROM {V} WHERE {{{{ch}}}}', {}, (0, 0, 6, 3)),
    ("Sell-In всего, руб", "scalar",
     f'SELECT ROUND(SUM("Sell-In, руб")) FROM {V} WHERE {{{{ch}}}}', {}, (6, 0, 6, 3)),
    ("Каналов", "scalar",
     f'SELECT COUNT(DISTINCT "Канал") FROM {V} WHERE {{{{ch}}}}', {}, (12, 0, 6, 3)),
    ("Sell-In по каналам, руб", "bar",
     f'SELECT "Канал", ROUND(SUM("Sell-In, руб")) AS "Sell-In, руб" FROM {V} WHERE {{{{ch}}}} '
     f'GROUP BY 1 ORDER BY 2 DESC NULLS LAST',
     {"graph.dimensions": ["Канал"], "graph.metrics": ["Sell-In, руб"]}, (0, 3, 18, 6)),
    ("Сводка по каналам", "table",
     f'SELECT "Канал", COUNT(*) AS "Сетей", ROUND(SUM("Sell-In, руб")) AS "Sell-In, руб", '
     f'ROUND(100*SUM("Sell-In, руб")/{TOT},1) AS "Доля, %" '
     f'FROM {V} WHERE {{{{ch}}}} GROUP BY 1 ORDER BY 3 DESC NULLS LAST', {}, (0, 9, 18, 6)),
    ("Клиенты по каналам (доля в Sell-In)", "table",
     f'SELECT "Сеть/группа", "Канал", ROUND("Sell-In, руб") AS "Sell-In, руб", '
     f'ROUND(100*"Sell-In, руб"/{TOT},2) AS "Доля в Sell-In, %", '
     f'ROUND("Sell-Out, шт") AS "Sell-Out, шт" '
     f'FROM {V} WHERE {{{{ch}}}} ORDER BY "Sell-In, руб" DESC NULLS LAST LIMIT 80', {}, (0, 15, 18, 12)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_channel_summary")
        if "Канал" in f:
            break
        time.sleep(3)
    if "Канал" not in f:
        raise SystemExit("Metabase ещё не увидел v_channel_summary — повтори через минуту.")
    mb.set_list(s, f["Канал"])
    tags = mb.dim_tag("ch", "Канал", f["Канал"], "string/=")
    params = [mb.param("p_ch", "Канал", "ch", "string/=", "string")]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": [mb.pmap("p_ch", cid, "ch")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
