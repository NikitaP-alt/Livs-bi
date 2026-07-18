"""Чинит/пере-привязывает фильтры Клиент/Товар/Год на дашбордах id=2 (Продажи) и id=3 (Остатки/закуп).

Зачем: карточки MBQL, а при пересоздании витрин Metabase меняет field id -> привязки фильтров
«сиротеют» и перестают фильтровать (так «умер» фильтр Клиент на остатках: смотрел на 239 вместо 227).
Скрипт заново привязывает параметры к ТЕКУЩИМ полям витрин (self-heal) + добавляет Товар на остатки.

Параметры дашбордов: pcl=Клиент, ppr=Товар, pyr=Год.
Запуск: docker compose exec -T app python -m app.fix_main_filters
"""
from . import mb

SO = {"pcl": "client", "ppr": "product", "pyr": "year"}     # продажи / закуп
STK = {"pcl": "client", "ppr": "product"}                    # остатки: год не применяем (снимок)

# карточка -> (витрина, какие параметры к ней привязать). Остатки читают из v_stock_latest!
CARD_VIEW = {
    # dash 2 — продажи (marts.v_sellout)
    40: ("v_sellout", SO), 41: ("v_sellout", SO), 42: ("v_sellout", SO), 43: ("v_sellout", SO),
    45: ("v_sellout", SO), 46: ("v_sellout", SO), 47: ("v_sellout", SO), 49: ("v_sellout", SO),
    48: ("v_sellout", {"pcl": "client", "ppr": "product"}),  # группируется по годам -> без Год
    44: ("v_stock_latest", STK),
    # dash 3 — остатки (v_stock_latest) + закуп (v_pos_purchase)
    50: ("v_stock_latest", STK), 52: ("v_stock_latest", STK),
    51: ("v_pos_purchase", SO), 53: ("v_pos_purchase", SO),
    54: ("v_pos_purchase", SO), 55: ("v_pos_purchase", SO),
}
# card 56 (карта, native) — фильтры не применяются, не трогаем


def main():
    s = mb.client()
    mb.sync(s)
    fids = {v: mb.field_ids(s, "marts", v)
            for v in ("v_sellout", "v_stock_latest", "v_pos_purchase")}
    for did in (2, 3):
        d = s.get(f"{mb.MB}/api/dashboard/{did}").json()
        out = []
        for dc in d["dashcards"]:
            cid = dc.get("card_id")
            row = {k: v for k, v in dc.items() if k != "card"}  # сохранить всё, кроме тяжёлого card
            if cid in CARD_VIEW:
                view, params = CARD_VIEW[cid]
                row["parameter_mappings"] = [
                    {"parameter_id": pid, "card_id": cid,
                     "target": ["dimension", ["field", fids[view][col], None]]}
                    for pid, col in params.items()]
            out.append(row)
        s.put(f"{mb.MB}/api/dashboard/{did}", json={"dashcards": out, "parameters": d["parameters"]})
        print(f"дашборд {did}: дашкарт {len(out)}, привязок пере-выставлено")


if __name__ == "__main__":
    main()
