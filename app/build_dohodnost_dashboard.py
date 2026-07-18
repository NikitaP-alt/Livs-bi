"""Дашборд «Доходность клиента (Коммерческая прибыль)» (нативный SQL, marts.v_dohodnost).

Формула руководителя: Комм.прибыль = Sell-In − Себест − Бюджет; Доходность% = КП / (Sell-In − Бюджет).
План 2026 из «Sales Retail». Фильтры: Канал / КАМ.
Запуск: docker compose exec -T app python -m app.build_dohodnost_dashboard
"""
import time
from . import mb

DASH = "Доходность клиента (Коммерческая прибыль)"
V = "marts.v_dohodnost"
F = "{{ch}} AND {{kam}}"

CARDS = [
    ("Средняя доходность план, %", "scalar",
     f'SELECT ROUND(100.0*SUM("Комм. прибыль план, руб")/'
     f'NULLIF(SUM("Sell-In 2026 план, руб")-SUM("Инвестиции (Бюджет), руб"),0),1) FROM {V} WHERE {F}',
     {}, (0, 0, 5, 3)),
    ("Sell-In 2026 план, руб", "scalar",
     f'SELECT ROUND(SUM("Sell-In 2026 план, руб")) FROM {V} WHERE {F}', {}, (5, 0, 4, 3)),
    ("Инвестиции (Бюджет), руб", "scalar",
     f'SELECT ROUND(SUM("Инвестиции (Бюджет), руб")) FROM {V} WHERE {F}', {}, (9, 0, 4, 3)),
    ("Комм. прибыль план, руб", "scalar",
     f'SELECT ROUND(SUM("Комм. прибыль план, руб")) FROM {V} WHERE {F}', {}, (13, 0, 5, 3)),
    ("Доходность план по клиентам, %", "bar",
     f'SELECT "Клиент", "Доходность план, %" FROM {V} WHERE {F} ORDER BY 2 DESC NULLS LAST',
     {"graph.dimensions": ["Клиент"], "graph.metrics": ["Доходность план, %"]}, (0, 3, 9, 7)),
    ("Комм. прибыль по клиентам, руб", "bar",
     f'SELECT "Клиент", "Комм. прибыль план, руб" FROM {V} WHERE {F} ORDER BY 2 DESC NULLS LAST',
     {"graph.dimensions": ["Клиент"], "graph.metrics": ["Комм. прибыль план, руб"]}, (9, 3, 9, 7)),
    ("Доходность по клиентам (детально)", "table",
     f'SELECT "Клиент","Канал","КАМ","Доходность план, %","Доходность прогноз, %","Доля в SI, %",'
     f'"Sell-In 2026 план, руб","Инвестиции (Бюджет), руб","Комм. прибыль план, руб" '
     f'FROM {V} WHERE {F} ORDER BY "Комм. прибыль план, руб" DESC NULLS LAST', {}, (0, 10, 18, 11)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_dohodnost")
        if "Канал" in f and "КАМ" in f:
            break
        time.sleep(3)
    if "Канал" not in f:
        raise SystemExit("Metabase ещё не увидел v_dohodnost — повтори через минуту.")
    for col in ("Канал", "КАМ"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("ch", "Канал", f["Канал"], "string/="))
    tags.update(mb.dim_tag("kam", "КАМ", f["КАМ"], "string/="))
    params = [
        mb.param("p_ch", "Канал", "ch", "string/=", "string"),
        mb.param("p_kam", "КАМ", "kam", "string/=", "string"),
    ]
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, tags)
        print(f"карточка [{cid}] {name}")
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": [mb.pmap("p_ch", cid, "ch"),
                                                 mb.pmap("p_kam", cid, "kam")]})
    did = mb.upsert_dashboard(s, DASH, dashcards, params)
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
