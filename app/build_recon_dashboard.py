"""Дашборд «Сверка Sell-In / Sell-Out» в Metabase (нативный SQL, marts.v_reconcile).

Фильтры дашборда: Год / Сеть ({{year}}/{{grp}}, field-filter'ы). Товара в витрине нет.
Идемпотентно. Запуск: docker compose exec -T app python -m app.build_recon_dashboard
"""
from . import mb

DASH = "Сверка Sell-In / Sell-Out"
# CTE: только группы, где есть и Sell-In (1С), и Sell-Out (отчёты), с учётом фильтров.
# ВАЖНО: marts.v_reconcile без алиаса (field-filter подставляет marts.v_reconcile."Год").
R = ('WITH r AS (SELECT "Сеть/группа" g, SUM("Sell-In, шт") si, SUM("Sell-In, руб") sir, '
     'SUM("Sell-Out, шт") so FROM marts.v_reconcile WHERE {{year}} AND {{grp}} GROUP BY 1 '
     'HAVING SUM("Sell-In, шт") IS NOT NULL AND SUM("Sell-Out, шт") IS NOT NULL) ')

CARDS = [
    ("Итого Sell-In, шт (сверяемые сети)", "scalar", R + "SELECT ROUND(SUM(si)) FROM r",
     {}, (0, 0, 6, 3)),
    ("Итого Sell-Out, шт (сверяемые сети)", "scalar", R + "SELECT ROUND(SUM(so)) FROM r",
     {}, (6, 0, 6, 3)),
    ("Общий Sell-Out / Sell-In", "scalar",
     R + "SELECT ROUND(SUM(so)/NULLIF(SUM(si),0),2) FROM r", {}, (12, 0, 6, 3)),
    ("Sell-In vs Sell-Out по сетям", "bar",
     R + 'SELECT g AS "Сеть", ROUND(si) AS "Sell-In, шт", ROUND(so) AS "Sell-Out, шт" '
         'FROM r ORDER BY so DESC',
     {"graph.dimensions": ["Сеть"], "graph.metrics": ["Sell-In, шт", "Sell-Out, шт"],
      "stackable.stack_type": None}, (0, 3, 18, 6)),
    ("Сверка по сетям (с коэффициентом)", "table",
     R + 'SELECT g AS "Сеть/группа", ROUND(si) AS "Sell-In, шт", ROUND(so) AS "Sell-Out, шт", '
         'ROUND(so/NULLIF(si,0),2) AS "Sell-Out/Sell-In" FROM r ORDER BY so DESC', {},
     (0, 9, 9, 7)),
    ("Динамика Sell-In vs Sell-Out по месяцам", "line",
     R + 'SELECT "Период" AS "Месяц", ROUND(SUM("Sell-In, шт")) AS "Sell-In, шт", '
         'ROUND(SUM("Sell-Out, шт")) AS "Sell-Out, шт" FROM marts.v_reconcile '
         'WHERE "Сеть/группа" IN (SELECT g FROM r) AND {{year}} AND {{grp}} '
         'GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Sell-In, шт", "Sell-Out, шт"]},
     (9, 9, 9, 7)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = mb.field_ids(s, "marts", "v_reconcile")
    for col in ("Год", "Сеть/группа"):
        mb.set_list(s, f[col])

    tags = {}
    tags.update(mb.dim_tag("year", "Год", f["Год"], "number/="))
    tags.update(mb.dim_tag("grp", "Сеть/группа", f["Сеть/группа"], "string/="))

    params = [
        mb.param("p_year", "Год", "year", "number/=", "number"),
        mb.param("p_grp", "Сеть/группа", "grp", "string/=", "string"),
    ]

    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({
            "id": -(i + 1), "card_id": cid, "row": r, "col": c, "size_x": sx, "size_y": sy,
            "visualization_settings": {},
            "parameter_mappings": [mb.pmap("p_year", cid, "year"),
                                   mb.pmap("p_grp", cid, "grp")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
