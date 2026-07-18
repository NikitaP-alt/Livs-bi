"""Дашборд «Доходность (Sell-In)» в Metabase (нативный SQL, marts.v_profit).

Фильтры дашборда: Год / Сеть / Товар (field-filter'ы, {{year}}/{{grp}}/{{prod}}).
Идемпотентно. Запуск: docker compose exec -T app python -m app.build_profit_dashboard
"""
from . import mb

DASH = "Доходность (Sell-In)"
V = "marts.v_profit"
W = "WHERE {{year}} AND {{grp}} AND {{prod}}"  # field-filter'ы -> 1=1 если пусто

# (col,row,size_x,size_y)
CARDS = [
    ("Выручка, руб (всего)", "scalar",
     f'SELECT ROUND(SUM("Выручка, руб")) FROM {V} {W}', {}, (0, 0, 6, 3)),
    ("Прибыль, руб (всего)", "scalar",
     f'SELECT ROUND(SUM("Прибыль, руб")) FROM {V} {W}', {}, (6, 0, 6, 3)),
    ("Рентабельность, % (всего)", "scalar",
     f'SELECT ROUND(100*SUM("Прибыль, руб")/NULLIF(SUM("Выручка, руб"),0),1) FROM {V} {W}',
     {}, (12, 0, 6, 3)),
    ("Выручка и прибыль по годам", "bar",
     f'SELECT "Год"::text AS "Год", ROUND(SUM("Выручка, руб")) AS "Выручка, руб", '
     f'ROUND(SUM("Прибыль, руб")) AS "Прибыль, руб" FROM {V} {W} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Год"], "graph.metrics": ["Выручка, руб", "Прибыль, руб"]},
     (0, 3, 18, 6)),
    ("Рентабельность по месяцам, %", "line",
     f'SELECT "Период" AS "Месяц", '
     f'ROUND(100*SUM("Прибыль, руб")/NULLIF(SUM("Выручка, руб"),0),1) AS "Рентаб., %" '
     f'FROM {V} {W} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Рентаб., %"]}, (0, 9, 18, 5)),
    ("Топ сетей по прибыли", "table",
     f'SELECT "Сеть/группа", ROUND(SUM("Выручка, руб")) AS "Выручка, руб", '
     f'ROUND(SUM("Прибыль, руб")) AS "Прибыль, руб", '
     f'ROUND(100*SUM("Прибыль, руб")/NULLIF(SUM("Выручка, руб"),0),1) AS "Рентаб., %" '
     f'FROM {V} {W} GROUP BY 1 ORDER BY 3 DESC NULLS LAST LIMIT 25', {}, (0, 14, 9, 9)),
    ("Топ товаров по прибыли", "table",
     f'SELECT "Товар", ROUND(SUM("Прибыль, руб")) AS "Прибыль, руб", '
     f'ROUND(100*SUM("Прибыль, руб")/NULLIF(SUM("Выручка, руб"),0),1) AS "Рентаб., %" '
     f'FROM {V} {W} GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 25', {}, (9, 14, 9, 9)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = mb.field_ids(s, "marts", "v_profit")
    for col in ("Год", "Сеть/группа", "Товар"):
        mb.set_list(s, f[col])

    tags = {}
    tags.update(mb.dim_tag("year", "Год", f["Год"], "number/="))
    tags.update(mb.dim_tag("grp", "Сеть/группа", f["Сеть/группа"], "string/="))
    tags.update(mb.dim_tag("prod", "Товар", f["Товар"], "string/="))

    params = [
        mb.param("p_year", "Год", "year", "number/=", "number"),
        mb.param("p_grp", "Сеть/группа", "grp", "string/=", "string"),
        mb.param("p_prod", "Товар", "prod", "string/=", "string"),
    ]

    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({
            "id": -(i + 1), "card_id": cid, "row": r, "col": c, "size_x": sx, "size_y": sy,
            "visualization_settings": {},
            "parameter_mappings": [mb.pmap("p_year", cid, "year"),
                                   mb.pmap("p_grp", cid, "grp"),
                                   mb.pmap("p_prod", cid, "prod")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
