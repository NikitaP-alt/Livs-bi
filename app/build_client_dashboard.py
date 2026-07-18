"""Дашборд «Клиент — разбор» (правки руководителя #1-3,6). marts.v_client_analysis.

Фильтры: Метрика (Sell-In/Sell-Out, переключение) + Клиент + Год. Виды: по годам, по месяцам (₽+шт: таблица+график),
по SKU (₽/шт, доля в Sell-In и Sell-Out, кол-во ТТ — только Sell-Out).
Запуск: docker compose exec -T app python -m app.build_client_dashboard
"""
import time
from . import mb

DASH = "Клиент — разбор"
V = "marts.v_client_analysis"

CARDS = [
    ("Динамика по годам", "bar",
     f'SELECT "Год"::text AS "Год", ROUND(SUM(rub)) AS "Руб", ROUND(SUM(qty)) AS "Шт" '
     f'FROM {V} WHERE {{{{metric}}}} AND {{{{client}}}} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Год"], "graph.metrics": ["Руб", "Шт"]}, (0, 0, 18, 6)),
    ("По месяцам (таблица)", "table",
     f'SELECT to_char("Период",\'YYYY-MM\') AS "Месяц", ROUND(SUM(rub)) AS "Руб", '
     f'ROUND(SUM(qty)) AS "Шт" FROM {V} WHERE {{{{metric}}}} AND {{{{client}}}} AND {{{{year}}}} '
     f'GROUP BY 1 ORDER BY 1', {}, (0, 6, 8, 8)),
    ("По месяцам (график)", "line",
     f'SELECT to_char("Период",\'YYYY-MM\') AS "Месяц", ROUND(SUM(rub)) AS "Руб", '
     f'ROUND(SUM(qty)) AS "Шт" FROM {V} WHERE {{{{metric}}}} AND {{{{client}}}} AND {{{{year}}}} '
     f'GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Руб", "Шт"]}, (8, 6, 10, 8)),
    ("По SKU (доли + ТТ)", "table",
     f'WITH cli AS (SELECT "Товар","Метрика",SUM(rub) r,SUM(qty) q,COUNT(DISTINCT tt_id) tt '
     f'FROM {V} WHERE {{{{client}}}} GROUP BY 1,2), '
     f'tot AS (SELECT "Метрика",SUM(r) tr FROM cli GROUP BY 1) '
     f'SELECT c."Товар", '
     f'ROUND(SUM(c.r) FILTER (WHERE c."Метрика"=\'Sell-In\')) AS "Sell-In, ₽", '
     f'ROUND(SUM(c.q) FILTER (WHERE c."Метрика"=\'Sell-In\')) AS "Sell-In, шт", '
     f'ROUND(SUM(c.r) FILTER (WHERE c."Метрика"=\'Sell-Out\')) AS "Sell-Out, ₽", '
     f'ROUND(SUM(c.q) FILTER (WHERE c."Метрика"=\'Sell-Out\')) AS "Sell-Out, шт", '
     f'ROUND(100*SUM(c.r) FILTER (WHERE c."Метрика"=\'Sell-In\')/'
     f'NULLIF((SELECT tr FROM tot WHERE "Метрика"=\'Sell-In\'),0),1) AS "Доля в SI, %", '
     f'ROUND(100*SUM(c.r) FILTER (WHERE c."Метрика"=\'Sell-Out\')/'
     f'NULLIF((SELECT tr FROM tot WHERE "Метрика"=\'Sell-Out\'),0),1) AS "Доля в SO, %", '
     f'MAX(c.tt) FILTER (WHERE c."Метрика"=\'Sell-Out\') AS "ТТ (Sell-Out)" '
     f'FROM cli c GROUP BY 1 ORDER BY 4 DESC NULLS LAST', {}, (0, 14, 18, 11)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_client_analysis")
        if "Метрика" in f and "Клиент" in f and "Год" in f:
            break
        time.sleep(3)
    if "Метрика" not in f:
        raise SystemExit("Metabase ещё не увидел v_client_analysis — повтори через минуту.")
    for col in ("Метрика", "Клиент", "Год"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("metric", "Метрика", f["Метрика"], "string/="))
    tags.update(mb.dim_tag("client", "Клиент", f["Клиент"], "string/="))
    tags.update(mb.dim_tag("year", "Год", f["Год"], "number/="))
    params = [
        {"id": "p_metric", "name": "Метрика", "slug": "metric", "type": "string/=",
         "sectionId": "string", "default": ["Sell-Out"]},
        {"id": "p_client", "name": "Клиент", "slug": "client", "type": "string/=",
         "sectionId": "string", "default": ["НеоФарм"]},
        {"id": "p_year", "name": "Год", "slug": "year", "type": "number/=",
         "sectionId": "number", "default": [2025]},
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        ct = {n: t for n, t in tags.items() if ("{{" + n + "}}") in sql}
        cid = mb.upsert_card(s, name, disp, sql, viz, ct)
        print(f"карточка [{cid}] {name}")
        pm = []
        if "metric" in ct:
            pm.append(mb.pmap("p_metric", cid, "metric"))
        if "client" in ct:
            pm.append(mb.pmap("p_client", cid, "client"))
        if "year" in ct:
            pm.append(mb.pmap("p_year", cid, "year"))
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": pm})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
