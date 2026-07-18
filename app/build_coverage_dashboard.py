"""Дашборд «Остатки: покрытие» в Metabase (нативный SQL, marts.v_stock_coverage).

Остаток + «на сколько хватит» (мес) при текущем темпе продаж, дрилл по товару и сети.
Фильтры: Сеть / Товар. Запуск: docker compose exec -T app python -m app.build_coverage_dashboard
"""
import time
from . import mb

DASH = "Остатки: покрытие"
V = "marts.v_stock_coverage"
F = "{{grp}} AND {{prod}}"

CARDS = [
    ("Остаток всего, шт", "scalar",
     f'SELECT ROUND(SUM("Остаток, шт")) FROM {V} WHERE {F}', {}, (0, 0, 6, 3)),
    ("Продажи в мес (ср. 3м), шт", "scalar",
     f'SELECT ROUND(SUM("Продажи в мес (ср. 3м), шт")) FROM {V} WHERE {F}', {}, (6, 0, 6, 3)),
    ("Общее покрытие, мес", "scalar",
     f'SELECT ROUND(SUM("Остаток, шт")/NULLIF(SUM("Продажи в мес (ср. 3м), шт"),0),1) '
     f'FROM {V} WHERE {F}', {}, (12, 0, 6, 3)),
    ("Покрытие по товарам (риск дефицита сверху)", "table",
     f'SELECT "Товар", ROUND(SUM("Остаток, шт")) AS "Остаток, шт", '
     f'ROUND(SUM("Продажи в мес (ср. 3м), шт"),1) AS "Продажи/мес", '
     f'ROUND(SUM("Остаток, шт")/NULLIF(SUM("Продажи в мес (ср. 3м), шт"),0),1) AS "Хватит на, мес" '
     f'FROM {V} WHERE {F} GROUP BY 1 ORDER BY 4 ASC NULLS LAST', {}, (0, 3, 9, 10)),
    ("Покрытие по сетям", "table",
     f'SELECT "Сеть/группа", ROUND(SUM("Остаток, шт")) AS "Остаток, шт", '
     f'ROUND(SUM("Остаток, шт")/NULLIF(SUM("Продажи в мес (ср. 3м), шт"),0),1) AS "Хватит на, мес" '
     f'FROM {V} WHERE {F} GROUP BY 1 ORDER BY 3 ASC NULLS LAST', {}, (9, 3, 9, 10)),
    ("Детально: сеть × товар (риск дефицита сверху)", "table",
     f'SELECT "Сеть/группа", "Товар", "Остаток, шт", "Продажи в мес (ср. 3м), шт", "Хватит на, мес" '
     f'FROM {V} WHERE {F} AND "Остаток, шт" > 0 ORDER BY "Хватит на, мес" ASC NULLS LAST LIMIT 100',
     {}, (0, 13, 18, 11)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_stock_coverage")
        if "Сеть/группа" in f and "Товар" in f:
            break
        time.sleep(3)
    if "Сеть/группа" not in f:
        raise SystemExit("Metabase ещё не увидел v_stock_coverage — повтори через минуту.")
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
