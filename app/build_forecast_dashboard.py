"""Дашборд «Прогноз (продажи и закупки)» (нативный SQL, marts.v_forecast).

Факт + прогноз по месяцам (run-rate × сезонность). Фильтры: Метрика (Продажи/Закупки) / Сеть.
Запуск: docker compose exec -T app python -m app.build_forecast_dashboard
"""
import time
from . import mb

DASH = "Прогноз (продажи и закупки)"
V = "marts.v_forecast"
F = "{{metric}} AND {{grp}}"

CARDS = [
    ("Факт 2026 (YtD), шт", "scalar",
     f'SELECT ROUND(SUM("Значение, шт")) FROM {V} WHERE {F} AND "Тип"=\'факт\' AND "Год"=2026',
     {}, (0, 0, 6, 3)),
    ("Прогноз до конца 2026, шт", "scalar",
     f'SELECT ROUND(SUM("Значение, шт")) FROM {V} WHERE {F} AND "Тип"=\'прогноз\' AND "Год"=2026',
     {}, (6, 0, 6, 3)),
    ("Прогноз 2027, шт", "scalar",
     f'SELECT ROUND(SUM("Значение, шт")) FROM {V} WHERE {F} AND "Тип"=\'прогноз\' AND "Год"=2027',
     {}, (12, 0, 6, 3)),
    ("Факт и прогноз по месяцам, шт", "line",
     f'SELECT "Период" AS "Месяц", '
     f'ROUND(SUM("Значение, шт") FILTER (WHERE "Тип"=\'факт\')) AS "Факт", '
     f'ROUND(SUM("Значение, шт") FILTER (WHERE "Тип"=\'прогноз\')) AS "Прогноз" '
     f'FROM {V} WHERE {F} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Факт", "Прогноз"]}, (0, 3, 18, 7)),
    ("Помесячно: факт и прогноз", "table",
     f'SELECT "Период" AS "Месяц", "Тип", "Значение, шт" FROM {V} WHERE {F} '
     f'AND "Период" >= \'2025-06-01\' ORDER BY "Период"', {}, (0, 10, 9, 9)),
    ("Прогноз по сетям (до конца 2026), шт", "table",
     f'SELECT "Сеть/группа", ROUND(SUM("Значение, шт")) AS "Прогноз ост.2026, шт" FROM {V} '
     f'WHERE {{{{metric}}}} AND "Тип"=\'прогноз\' AND "Год"=2026 AND "Сеть/группа"<>\'ИТОГО\' '
     f'GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 20', {}, (9, 10, 9, 9)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_forecast")
        if "Метрика" in f and "Сеть/группа" in f:
            break
        time.sleep(3)
    if "Метрика" not in f:
        raise SystemExit("Metabase ещё не увидел v_forecast — повтори через минуту.")
    for col in ("Метрика", "Сеть/группа"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("metric", "Метрика", f["Метрика"], "string/="))
    tags.update(mb.dim_tag("grp", "Сеть/группа", f["Сеть/группа"], "string/="))
    params = [
        {"id": "p_metric", "name": "Метрика", "slug": "metric", "type": "string/=",
         "sectionId": "string", "default": ["Продажи"]},
        {"id": "p_grp", "name": "Сеть/группа", "slug": "grp", "type": "string/=",
         "sectionId": "string", "default": ["ИТОГО"]},
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        card_tags = {n: t for n, t in tags.items() if ("{{" + n + "}}") in sql}
        cid = mb.upsert_card(s, name, disp, sql, viz, card_tags)
        print(f"карточка [{cid}] {name}")
        pm = [mb.pmap("p_metric", cid, "metric")]
        if "grp" in card_tags:
            pm.append(mb.pmap("p_grp", cid, "grp"))
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": pm})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
