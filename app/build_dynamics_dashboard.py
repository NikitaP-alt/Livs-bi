"""Дашборд «Динамика и прирост» в Metabase (нативный SQL, marts.v_dynamics).

Продажи и закупки по периодам + прирост MoM / QoQ / YoY / YtD.
Фильтры: Сеть / Товар (Год НЕ ставим — иначе ломается расчёт прироста год-к-году).
Запуск: docker compose exec -T app python -m app.build_dynamics_dashboard
"""
from . import mb

DASH = "Динамика и прирост"
V = "marts.v_dynamics"
F = "{{grp}} AND {{prod}}"  # field-filter'ы -> 1=1 если пусто

# «на последнюю дату»: последний год и его максимальный месяц (для честного YtD)
CUT = ('cutoff AS (SELECT MAX(EXTRACT(MONTH FROM "Период"))::int m, MAX("Год") y '
       f'FROM {V} WHERE "Год"=(SELECT MAX("Год") FROM {V}))')

CARDS = [
    ("Продажи YtD (посл. год), шт", "scalar",
     f'WITH {CUT} SELECT ROUND(SUM("Продажи, шт")) FROM {V} '
     f'WHERE {F} AND "Год"=(SELECT y FROM cutoff) '
     f'AND EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)', {}, (0, 0, 6, 3)),
    ("Прирост продаж YtD, % (год к году)", "scalar",
     f'WITH {CUT}, '
     f'cur AS (SELECT SUM("Продажи, шт") v FROM {V} WHERE {F} AND "Год"=(SELECT y FROM cutoff) '
     f'AND EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)), '
     f'prv AS (SELECT SUM("Продажи, шт") v FROM {V} WHERE {F} AND "Год"=(SELECT y-1 FROM cutoff) '
     f'AND EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)) '
     f'SELECT ROUND(100*((SELECT v FROM cur)-(SELECT v FROM prv))/NULLIF((SELECT v FROM prv),0),1)',
     {}, (6, 0, 6, 3)),
    ("Закупки YtD (посл. год), шт", "scalar",
     f'WITH {CUT} SELECT ROUND(SUM("Закупки, шт")) FROM {V} '
     f'WHERE {F} AND "Год"=(SELECT y FROM cutoff) '
     f'AND EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)', {}, (12, 0, 6, 3)),
    ("Продажи и закупки по месяцам", "line",
     f'SELECT date_trunc(\'month\',"Период") AS "Месяц", '
     f'ROUND(SUM("Продажи, шт")) AS "Продажи, шт", ROUND(SUM("Закупки, шт")) AS "Закупки, шт" '
     f'FROM {V} WHERE {F} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Продажи, шт", "Закупки, шт"]}, (0, 3, 18, 6)),
    ("Годовой прирост (YoY)", "table",
     f'WITH agg AS (SELECT "Год" y, SUM("Продажи, шт") so, SUM("Закупки, шт") si '
     f'FROM {V} WHERE {F} GROUP BY 1) '
     f'SELECT y AS "Год", ROUND(so) AS "Продажи, шт", '
     f'ROUND(100*(so-LAG(so) OVER(ORDER BY y))/NULLIF(LAG(so) OVER(ORDER BY y),0),1) AS "Прод. YoY %", '
     f'ROUND(si) AS "Закупки, шт", '
     f'ROUND(100*(si-LAG(si) OVER(ORDER BY y))/NULLIF(LAG(si) OVER(ORDER BY y),0),1) AS "Зак. YoY %" '
     f'FROM agg ORDER BY y', {}, (0, 9, 9, 5)),
    ("YtD по годам (сравнимое окно)", "table",
     f'WITH {CUT}, agg AS (SELECT "Год" y, '
     f'SUM("Продажи, шт") FILTER (WHERE EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)) so, '
     f'SUM("Закупки, шт") FILTER (WHERE EXTRACT(MONTH FROM "Период")<=(SELECT m FROM cutoff)) si '
     f'FROM {V} WHERE {F} GROUP BY 1) '
     f'SELECT y AS "Год", ROUND(so) AS "Продажи YtD, шт", '
     f'ROUND(100*(so-LAG(so) OVER(ORDER BY y))/NULLIF(LAG(so) OVER(ORDER BY y),0),1) AS "Прод. YoY %", '
     f'ROUND(si) AS "Закупки YtD, шт" FROM agg ORDER BY y', {}, (9, 9, 9, 5)),
    ("Поквартальный прирост (QoQ / YoY)", "table",
     f'WITH agg AS (SELECT date_trunc(\'quarter\',"Период") q, SUM("Продажи, шт") so '
     f'FROM {V} WHERE {F} GROUP BY 1) '
     f'SELECT EXTRACT(YEAR FROM q)::int || \' Q\' || EXTRACT(QUARTER FROM q)::int AS "Квартал", '
     f'ROUND(so) AS "Продажи, шт", '
     f'ROUND(100*(so-LAG(so,1) OVER(ORDER BY q))/NULLIF(LAG(so,1) OVER(ORDER BY q),0),1) AS "QoQ %", '
     f'ROUND(100*(so-LAG(so,4) OVER(ORDER BY q))/NULLIF(LAG(so,4) OVER(ORDER BY q),0),1) AS "YoY %" '
     f'FROM agg ORDER BY q DESC', {}, (0, 14, 9, 9)),
    ("Помесячный прирост (MoM / YoY)", "table",
     f'WITH spine AS (SELECT generate_series((SELECT date_trunc(\'month\',MIN("Период")) FROM {V}), '
     f'(SELECT date_trunc(\'month\',MAX("Период")) FROM {V}), interval \'1 month\') p), '
     f'agg AS (SELECT date_trunc(\'month\',"Период") p, SUM("Продажи, шт") so, SUM("Закупки, шт") si '
     f'FROM {V} WHERE {F} GROUP BY 1), '
     f'j AS (SELECT s.p, COALESCE(a.so,0) so, COALESCE(a.si,0) si FROM spine s LEFT JOIN agg a ON a.p=s.p) '
     f'SELECT to_char(p,\'YYYY-MM\') AS "Месяц", ROUND(so) AS "Продажи, шт", '
     f'ROUND(100*(so-LAG(so,1) OVER(ORDER BY p))/NULLIF(LAG(so,1) OVER(ORDER BY p),0),1) AS "MoM %", '
     f'ROUND(100*(so-LAG(so,12) OVER(ORDER BY p))/NULLIF(LAG(so,12) OVER(ORDER BY p),0),1) AS "YoY %", '
     f'ROUND(si) AS "Закупки, шт" FROM j ORDER BY p DESC', {}, (9, 14, 9, 9)),
]


def main():
    import time
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):  # синк схемы асинхронный — ждём появления полей витрины
        f = mb.field_ids(s, "marts", "v_dynamics")
        if "Сеть/группа" in f and "Товар" in f:
            break
        time.sleep(3)
    if "Сеть/группа" not in f:
        raise SystemExit("Metabase ещё не увидел marts.v_dynamics — повтори запуск через минуту.")
    for col in ("Сеть/группа", "Товар"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("grp", "Сеть/группа", f["Сеть/группа"], "string/="))
    tags.update(mb.dim_tag("prod", "Товар", f["Товар"], "string/="))
    params = [
        mb.param("p_grp", "Сеть/группа", "grp", "string/=", "string"),
        mb.param("p_prod", "Товар", "prod", "string/=", "string"),
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": [mb.pmap("p_grp", cid, "grp"),
                                                 mb.pmap("p_prod", cid, "prod")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
