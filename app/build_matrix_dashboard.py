"""Дашборд «Матрица — соблюдение ассортимента» (нативный SQL, marts.v_matrix — вычисляемая).

Соблюдение = доля активных ТТ сети, где товар реально на стоке. Считается из остатков, обновляется сам.
Фильтры: Сеть (по умолчанию Диалог) + Товар. Работает для всех сетей с поточечными остатками.
Запуск: docker compose exec -T app python -m app.build_matrix_dashboard
"""
import time
from . import mb

DASH = "Матрица — соблюдение (пример: Диалог)"  # имя сохранено -> обновляем существующий дашборд
V = "marts.v_matrix"
LASTG = f'(SELECT MAX("Период") FROM {V} WHERE {{{{grp}}}})'  # последний снимок выбранной сети
F = "{{grp}} AND {{prod}}"

CARDS = [
    ("Авторизовано ТТ (посл. месяц)", "scalar",
     f'SELECT MAX("Авторизовано ТТ") FROM {V} WHERE {{{{grp}}}} AND "Период"={LASTG}',
     {}, (0, 0, 6, 3)),
    ("Среднее соблюдение (посл. месяц), %", "scalar",
     f'SELECT ROUND(AVG("Соблюдение, %"),1) FROM {V} WHERE {F} AND "Период"={LASTG}',
     {}, (6, 0, 6, 3)),
    ("Товаров в матрице", "scalar",
     f'SELECT COUNT(DISTINCT "Товар") FROM {V} WHERE {F}', {}, (12, 0, 6, 3)),
    ("Соблюдение матрицы по месяцам, %", "line",
     f'SELECT "Период" AS "Месяц", ROUND(AVG("Соблюдение, %"),1) AS "Соблюдение, %" '
     f'FROM {V} WHERE {F} GROUP BY 1 ORDER BY 1',
     {"graph.dimensions": ["Месяц"], "graph.metrics": ["Соблюдение, %"]}, (0, 3, 18, 6)),
    ("По товарам (посл. месяц) — снизу худшее соблюдение", "table",
     f'SELECT "Товар", MAX("Авторизовано ТТ") AS "Авторизовано ТТ", '
     f'MAX("ТТ со стоком") AS "ТТ со стоком", MAX("Соблюдение, %") AS "Соблюдение, %" '
     f'FROM {V} WHERE {F} AND "Период"={LASTG} GROUP BY 1 ORDER BY 4 ASC', {}, (0, 9, 9, 9)),
    ("Соблюдение по товарам (посл. месяц), %", "bar",
     f'SELECT "Товар", MAX("Соблюдение, %") AS "Соблюдение, %" '
     f'FROM {V} WHERE {F} AND "Период"={LASTG} GROUP BY 1 ORDER BY 2 DESC',
     {"graph.dimensions": ["Товар"], "graph.metrics": ["Соблюдение, %"]}, (9, 9, 9, 9)),
]


def main():
    s = mb.client()
    mb.sync(s)
    f = {}
    for _ in range(15):
        f = mb.field_ids(s, "marts", "v_matrix")
        if "Сеть/группа" in f and "Товар" in f:
            break
        time.sleep(3)
    if "Сеть/группа" not in f:
        raise SystemExit("Metabase ещё не увидел v_matrix — повтори через минуту.")
    for col in ("Сеть/группа", "Товар"):
        mb.set_list(s, f[col])
    tags = {}
    tags.update(mb.dim_tag("grp", "Сеть/группа", f["Сеть/группа"], "string/="))
    tags.update(mb.dim_tag("prod", "Товар", f["Товар"], "string/="))
    params = [
        {"id": "p_grp", "name": "Сеть/группа", "slug": "grp", "type": "string/=",
         "sectionId": "string", "default": ["Диалог"]},   # открывается на Диалоге
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
