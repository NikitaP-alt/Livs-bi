"""Дашборд «План-факт помесячно» (зад.9, помесячный слой) на marts.v_plan_fact_month.

Фильтры: Клиент · Показатель (по умолч. «Sell In, руб») · Год (по умолч. 2026).
Карточки: 3 KPI (План/Факт/Выполнение за год) · график План vs Факт по месяцам · таблица по месяцам ·
таблица по клиентам (обзор, без фильтра клиента). Запуск: docker compose exec -T app python -m app.build_plan_month_dashboard
"""
from . import mb

V = "marts.v_plan_fact_month"
FLT = "{{client}} AND {{metric}} AND {{year}}"     # клиент+показатель+год
FMY = "{{metric}} AND {{year}}"                     # без клиента (обзор по всем)
# выполнение = (факт по закрытым + прогноз по будущим) / план
DONE = "ROUND(100.0*SUM(expected)/NULLIF(SUM(plan),0),1)"

CARDS = [
    ("ПФ·мес — План за год, ∑", "scalar",
     f"SELECT ROUND(SUM(plan)) FROM {V} WHERE {FLT}", {}, (0, 0, 6, 3)),
    ("ПФ·мес — Факт+прогноз за год, ∑", "scalar",
     f"SELECT ROUND(SUM(expected)) FROM {V} WHERE {FLT}", {}, (6, 0, 6, 3)),
    ("ПФ·мес — Выполнение за год, %", "scalar",
     f"SELECT {DONE} FROM {V} WHERE {FLT}", {}, (12, 0, 6, 3)),
    ("ПФ·мес — План vs Факт/прогноз по месяцам", "bar",
     f'SELECT month AS "Месяц", ROUND(SUM(plan)) AS "План", ROUND(SUM(expected)) AS "Факт/прогноз" '
     f'FROM {V} WHERE {FLT} GROUP BY month, month_num ORDER BY month_num',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["План", "Факт/прогноз"]}, (0, 3, 18, 7)),
    ("ПФ·мес — Таблица по месяцам", "table",
     f'SELECT month AS "Месяц", ROUND(SUM(plan)) AS "План", ROUND(SUM(fact)) AS "Факт", '
     f'ROUND(SUM(forecast)) AS "Прогноз", ROUND(SUM(expected)) AS "Факт/прогноз", '
     f'{DONE} AS "Выполнение, %" '
     f'FROM {V} WHERE {FLT} GROUP BY month, month_num ORDER BY month_num',
     {}, (0, 10, 10, 9)),
    ("ПФ·мес — По клиентам (обзор)", "table",
     f'SELECT client AS "Клиент", ROUND(SUM(plan)) AS "План", ROUND(SUM(expected)) AS "Факт/прогноз", '
     f'{DONE} AS "Выполнение, %" FROM {V} WHERE {FMY} '
     f'GROUP BY client ORDER BY SUM(plan) DESC NULLS LAST',
     {}, (10, 10, 8, 9)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = mb.field_ids(s, "marts", "v_plan_fact_month")
    for col in ("client", "metric", "year"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("client", "Клиент", f["client"], "string/="))
    tags.update(mb.dim_tag("metric", "Показатель", f["metric"], "string/="))
    tags.update(mb.dim_tag("year", "Год", f["year"], "number/="))
    params = [
        mb.param("p_client", "Клиент", "client", "string/=", "string"),
        {"id": "p_metric", "name": "Показатель", "slug": "metric", "type": "string/=",
         "sectionId": "string", "default": ["Sell In, руб"]},
        {"id": "p_year", "name": "Год", "slug": "year", "type": "number/=",
         "sectionId": "number", "default": [2026]},
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        ct = {n: t for n, t in tags.items() if ("{{" + n + "}}") in sql}
        cid = mb.upsert_card(s, name, disp, sql, viz, ct)
        print(f"карточка [{cid}] {name}")
        pm = []
        for slug, tag in (("p_client", "client"), ("p_metric", "metric"), ("p_year", "year")):
            if tag in ct:
                pm.append(mb.pmap(slug, cid, tag))
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": pm})
    did = mb.upsert_dashboard(s, "План-факт помесячно", dashcards, params)
    # положить в коллекцию «LIVS BI» (id=5), как остальные
    s.put(f"{mb.MB}/api/dashboard/{did}", json={"collection_id": 5})
    print(f"\nДашборд «План-факт помесячно» готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
