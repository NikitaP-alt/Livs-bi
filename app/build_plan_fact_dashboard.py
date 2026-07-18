"""Дашборд «План-факт» (нативный SQL, marts.v_plan_fact).

План vs Факт/Прогноз по клиентам и кварталам, выполнение %. Из «ПЛАН ФАКТ 2026».
Фильтры: Показатель (по умолч. Sell In, шт) / Клиент / Канал.
Запуск: docker compose exec -T app python -m app.build_plan_fact_dashboard
"""
import time
from . import mb

DASH = "План-факт (Sell-In / Sell-Out)"
V = "marts.v_plan_fact"
F = "{{metric}} AND {{client}} AND {{ch}}"
Y = f'{F} AND "Период"=\'2026\''          # год
Q = f"{F} AND \"Период\" LIKE '_Q26'"     # кварталы

CARDS = [
    ("План 2026", "scalar", f'SELECT ROUND(SUM("План")) FROM {V} WHERE {Y}', {}, (0, 0, 6, 3)),
    ("Факт / Прогноз 2026", "scalar",
     f'SELECT ROUND(SUM("Факт/Прогноз")) FROM {V} WHERE {Y}', {}, (6, 0, 6, 3)),
    ("Выполнение плана, %", "scalar",
     f'SELECT ROUND(100.0*SUM("Факт/Прогноз")/NULLIF(SUM("План"),0),1) FROM {V} WHERE {Y}',
     {}, (12, 0, 6, 3)),
    ("План vs Факт/Прогноз по кварталам", "bar",
     f'SELECT "Период" AS "Квартал", ROUND(SUM("План")) AS "План", '
     f'ROUND(SUM("Факт/Прогноз")) AS "Факт/Прогноз" FROM {V} WHERE {Q} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Квартал"], "graph.metrics": ["План", "Факт/Прогноз"]}, (0, 3, 9, 7)),
    ("Выполнение по клиентам, %", "bar",
     f'SELECT "Клиент", ROUND(100.0*SUM("Факт/Прогноз")/NULLIF(SUM("План"),0),1) AS "Выполнение, %" '
     f'FROM {V} WHERE {Y} GROUP BY 1 ORDER BY 2 DESC NULLS LAST',
     {"graph.dimensions": ["Клиент"], "graph.metrics": ["Выполнение, %"]}, (9, 3, 9, 7)),
    ("План-факт по клиентам (2026)", "table",
     f'SELECT "Клиент","Канал",ROUND(SUM("План")) AS "План",ROUND(SUM("Факт/Прогноз")) AS "Факт/Прогноз",'
     f'ROUND(100.0*SUM("Факт/Прогноз")/NULLIF(SUM("План"),0),1) AS "Выполнение, %" '
     f'FROM {V} WHERE {Y} GROUP BY 1,2 ORDER BY 3 DESC NULLS LAST', {}, (0, 10, 18, 11)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_plan_fact")
        if "Показатель" in f and "Клиент" in f:
            break
        time.sleep(3)
    if "Показатель" not in f:
        raise SystemExit("Metabase ещё не увидел v_plan_fact — повтори через минуту.")
    for col in ("Показатель", "Клиент", "Канал"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("metric", "Показатель", f["Показатель"], "string/="))
    tags.update(mb.dim_tag("client", "Клиент", f["Клиент"], "string/="))
    tags.update(mb.dim_tag("ch", "Канал", f["Канал"], "string/="))
    params = [
        {"id": "p_metric", "name": "Показатель", "slug": "metric", "type": "string/=",
         "sectionId": "string", "default": ["Sell In, шт"]},
        mb.param("p_client", "Клиент", "client", "string/=", "string"),
        mb.param("p_ch", "Канал", "ch", "string/=", "string"),
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": [mb.pmap("p_metric", cid, "metric"),
                                                 mb.pmap("p_client", cid, "client"),
                                                 mb.pmap("p_ch", cid, "ch")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
