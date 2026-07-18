"""Дашборд «Проверка данных (контроль качества)» — страховка при самостоятельной загрузке.
Подсвечивает: резкие скачки (MoM), аномальные строки, кто не сдал отчёт, неклассиф. товары.
Запуск: docker compose exec -T app python -m app.build_dq_dashboard
"""
import time
from . import mb

DASH = "Проверка данных (контроль качества)"
DQ = "marts.v_dq_monthly"

CARDS = [
    ("Резких скачков за 4 мес (±50%)", "scalar",
     f'SELECT COUNT(*) FROM {DQ} WHERE ABS("Изменение, %")>=50 AND "Пред. месяц" IS NOT NULL '
     f'AND "Период" >= (SELECT MAX("Период") FROM {DQ}) - INTERVAL \'4 months\'', {}, (0, 0, 6, 3)),
    ("Сетей не сдали свежий месяц", "scalar",
     f'WITH mx AS (SELECT MAX("Период") m FROM {DQ}) '
     f'SELECT COUNT(*) FROM (SELECT "Сеть/группа" FROM {DQ} WHERE "Метрика"=\'Продажи\' '
     f'GROUP BY 1 HAVING MAX("Период") < (SELECT m FROM mx)) t', {}, (6, 0, 6, 3)),
    ("Неклассифиц. товаров (SKU)", "scalar",
     "SELECT COUNT(*) FROM core.dim_sku s LEFT JOIN core.dim_product p ON p.product_id=s.product_id "
     "WHERE s.product_id IS NULL OR p.name LIKE '❓%'", {}, (12, 0, 6, 3)),
    ("🔴 Резкие скачки месяц-к-месяцу (проверить!)", "table",
     f'SELECT "Метрика","Сеть/группа", to_char("Период",\'YYYY-MM\') AS "Период", '
     f'ROUND("Значение") AS "Значение", ROUND("Пред. месяц") AS "Пред. месяц", "Изменение, %" '
     f'FROM {DQ} WHERE ABS("Изменение, %")>=50 AND "Пред. месяц" IS NOT NULL '
     f'AND "Период" >= (SELECT MAX("Период") FROM {DQ}) - INTERVAL \'4 months\' '
     f'ORDER BY ABS("Изменение, %") DESC LIMIT 40', {}, (0, 3, 18, 8)),
    ("🔴 Аномальные строки (qty>20000 или <0)", "table",
     "SELECT * FROM ("
     "SELECT 'Продажи' AS \"Метрика\", c.name AS \"Клиент\", to_char(f.period,'YYYY-MM') AS \"Период\", "
     "s.name AS \"Товар\", ROUND(f.qty) AS \"Кол-во\" "
     "FROM core.fact_sellout f JOIN core.dim_client c ON c.client_id=f.client_id "
     "JOIN core.dim_sku s ON s.sku_id=f.sku_id "
     "UNION ALL SELECT 'Остатки', c.name, to_char(f.snapshot_date,'YYYY-MM'), s.name, ROUND(f.qty) "
     "FROM core.fact_stock f JOIN core.dim_client c ON c.client_id=f.client_id "
     "JOIN core.dim_sku s ON s.sku_id=f.sku_id "
     "UNION ALL SELECT 'Закуп', c.name, to_char(f.period,'YYYY-MM'), s.name, ROUND(f.qty) "
     "FROM core.fact_pos_purchase f JOIN core.dim_client c ON c.client_id=f.client_id "
     "JOIN core.dim_sku s ON s.sku_id=f.sku_id) t "
     "WHERE \"Кол-во\">20000 OR \"Кол-во\"<0 ORDER BY \"Кол-во\" DESC LIMIT 30", {}, (0, 11, 9, 8)),
    ("🟡 Кто отстаёт по отчётам (последний период)", "table",
     f'WITH mx AS (SELECT MAX("Период") m FROM {DQ}) '
     f'SELECT "Метрика","Сеть/группа", to_char(MAX("Период"),\'YYYY-MM\') AS "Последний период", '
     f'((EXTRACT(YEAR FROM (SELECT m FROM mx))*12+EXTRACT(MONTH FROM (SELECT m FROM mx))) '
     f'-(EXTRACT(YEAR FROM MAX("Период"))*12+EXTRACT(MONTH FROM MAX("Период"))))::int AS "Отстаёт, мес" '
     f'FROM {DQ} GROUP BY 1,2 HAVING MAX("Период") < (SELECT m FROM mx) ORDER BY 4 DESC LIMIT 30',
     {}, (9, 11, 9, 8)),
]


def main():
    s = mb.client()
    mb.sync(s)
    for _ in range(15):
        if "Изменение, %" in mb.field_ids(s, "marts", "v_dq_monthly"):
            break
        time.sleep(3)
    dashcards = []
    for i, (name, disp, sql, viz, (c, r, sx, sy)) in enumerate(CARDS):
        cid = mb.upsert_card(s, name, disp, sql, viz, {})
        print(f"карточка [{cid}] {name}")
        dashcards.append({"id": -(i + 1), "card_id": cid, "row": r, "col": c,
                          "size_x": sx, "size_y": sy, "visualization_settings": {},
                          "parameter_mappings": []})
    did = mb.upsert_dashboard(s, DASH, dashcards, [])
    # в коллекцию LIVS BI
    s.put(f"{mb.MB}/api/dashboard/{did}", json={"collection_id": 5})
    print(f"\nДашборд готов: http://localhost:3000/dashboard/{did}")


if __name__ == "__main__":
    main()
