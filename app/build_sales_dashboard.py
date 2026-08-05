"""Пересборка дашборда «Продажи» (бывш. id=2 «Продажи и остатки») по правкам руководителя.

Раскладка: 3 KPI (шт/руб/ТТ) · продажи по годам руб+прирост / шт+прирост · пивот год×месяц (шт)+итого+%
· всего шт + по городам · таблица SKU×месяц. Фильтры: Клиент / Год / Товар.
Перестраивает дашборд id=2 НА МЕСТЕ (публичная ссылка сохраняется). Запуск: docker compose exec -T app python -m app.build_sales_dashboard
"""
import time
from . import mb

DID = 2
V = "marts.v_sellout"
FA = "{{client}} AND {{year}} AND {{product}}"    # все фильтры
FC = "{{client}} AND {{product}}"                 # без года (разрез по годам)
MONTHS = [("Янв", 1), ("Фев", 2), ("Мар", 3), ("Апр", 4), ("Май", 5), ("Июн", 6),
          ("Июл", 7), ("Авг", 8), ("Сен", 9), ("Окт", 10), ("Ноя", 11), ("Дек", 12)]
PIV = ", ".join(f'ROUND(SUM(qty) FILTER (WHERE month_num={n})) AS "{nm}"' for nm, n in MONTHS)
# помесячно + подытог по кварталу после каждых трёх месяцев: Янв Фев Мар «1 кв» Апр Май Июн «2 кв» …
_QM = {1: [("Янв", 1), ("Фев", 2), ("Мар", 3)], 2: [("Апр", 4), ("Май", 5), ("Июн", 6)],
       3: [("Июл", 7), ("Авг", 8), ("Сен", 9)], 4: [("Окт", 10), ("Ноя", 11), ("Дек", 12)]}
_COLS = []
for _q in (1, 2, 3, 4):
    for _nm, _mn in _QM[_q]:
        _COLS.append(f'ROUND(SUM(qty) FILTER (WHERE month_num={_mn})) AS "{_nm}"')
    _COLS.append(f'ROUND(SUM(qty) FILTER (WHERE quarter={_q})) AS "{_q} кв"')
MQPIV = ", ".join(_COLS)
YOY = 'ROUND(100*({m}-LAG({m}) OVER (ORDER BY year))/NULLIF(LAG({m}) OVER (ORDER BY year),0),0)'

CARDS = [
    ("Продажи, шт", "scalar", f'SELECT ROUND(SUM(qty)) FROM {V} WHERE {FA}', {}, (0, 0, 6, 3)),
    ("Продажи, руб", "scalar", f'SELECT ROUND(SUM(rub_est)) FROM {V} WHERE {FA}', {}, (6, 0, 6, 3)),
    ("Торговых точек", "scalar", f'SELECT COUNT(DISTINCT tt_id) FROM {V} WHERE {FA}', {}, (12, 0, 6, 3)),
    ("Продажи по годам, руб (+прирост)", "bar",
     f'SELECT year::text AS "Год", ROUND(SUM(rub_est)) AS "Руб", '
     f'{YOY.format(m="SUM(rub_est)")} AS "Прирост, %" FROM {V} WHERE {FC} GROUP BY year ORDER BY year',
     {"graph.dimensions": ["Год"], "graph.metrics": ["Руб", "Прирост, %"], "graph.y_axis.auto_split": True},
     (0, 3, 9, 7)),
    ("Продажи по годам, шт (+прирост)", "bar",
     f'SELECT year::text AS "Год", ROUND(SUM(qty)) AS "Шт", '
     f'{YOY.format(m="SUM(qty)")} AS "Прирост, %" FROM {V} WHERE {FC} GROUP BY year ORDER BY year',
     {"graph.dimensions": ["Год"], "graph.metrics": ["Шт", "Прирост, %"], "graph.y_axis.auto_split": True},
     (9, 3, 9, 7)),
    ("Продажи по месяцам и кварталам, шт", "table",
     f'SELECT year AS "Год", {MQPIV}, ROUND(SUM(qty)) AS "Итого за год", '
     f'{YOY.format(m="SUM(qty)")} AS "Прирост, %" FROM {V} WHERE {FC} GROUP BY year ORDER BY year',
     {}, (0, 10, 18, 7)),
    ("Продажи всего, шт", "scalar", f'SELECT ROUND(SUM(qty)) FROM {V} WHERE {FC}', {}, (0, 17, 5, 5)),
    ("Продажи по городам, шт", "bar",
     f'SELECT city AS "Город", ROUND(SUM(qty)) AS "Шт" FROM {V} WHERE {FA} '
     f'GROUP BY 1 ORDER BY 2 DESC NULLS LAST LIMIT 15',
     {"graph.dimensions": ["Город"], "graph.metrics": ["Шт"]}, (5, 17, 13, 9)),
    ("Продажи по SKU и месяцам, шт", "table",
     f'SELECT product AS "Товар", {PIV}, ROUND(SUM(qty)) AS "Итого" '
     f'FROM {V} WHERE {FA} GROUP BY product ORDER BY SUM(qty) DESC', {}, (0, 26, 18, 10)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = mb.field_ids(s, "marts", "v_sellout")
    for col in ("client", "year", "product"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("client", "Клиент", f["client"], "string/="))
    tags.update(mb.dim_tag("year", "Год", f["year"], "number/="))
    tags.update(mb.dim_tag("product", "Товар", f["product"], "string/="))
    params = [
        mb.param("p_client", "Клиент", "client", "string/=", "string"),
        {"id": "p_year", "name": "Год", "slug": "year", "type": "number/=", "sectionId": "number",
         "default": [2025]},
        mb.param("p_product", "Товар", "product", "string/=", "string"),
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        ct = {n: t for n, t in tags.items() if ("{{" + n + "}}") in sql}
        cid = mb.upsert_card(s, name, disp, sql, viz, ct)
        print(f"карточка [{cid}] {name}")
        pm = []
        for slug, tag in (("p_client", "client"), ("p_year", "year"), ("p_product", "product")):
            if tag in ct:
                pm.append(mb.pmap(slug, cid, tag))
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": pm})
    # перестроить дашборд id=2 на месте + переименовать
    s.put(f"{mb.MB}/api/dashboard/{DID}",
          json={"name": "Продажи", "dashcards": dashcards, "parameters": params, "collection_id": 5})
    print(f"\nДашборд «Продажи» пересобран: http://localhost:3000/dashboard/{DID}")


if __name__ == "__main__":
    main()
