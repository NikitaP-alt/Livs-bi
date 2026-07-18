"""Загрузка выгрузки 1С (Sell-In) из сводного пивота.
Строки: Менеджер -> Покупатель(юрлицо) -> Номенклатура; столбцы: месяц × [Количество, Выручка, Рентаб., Себест.].
Берём строки-товары ЛИВС, привязываем к текущему Покупателю. -> core.fact_sellin (кол-во + выручка руб).

Запуск: docker compose exec -T app python -m app.load_1c
"""
import re
from datetime import date

import pandas as pd
from sqlalchemy import text

from .config import get_engine
from .mapping import get_or_create_client

FILE = "incoming/1С/1С.xlsx"
SRC = "1С.xlsx"
RU = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "май": 5, "июн": 6,
      "июл": 7, "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
LEGAL = re.compile(r"\b(ооо|зао|оао|пао|нао|ао|ип|чп|пбоюл)\b")


def _mon(s):
    s = str(s).lower()
    y = re.search(r"20\d{2}", s)
    if not y:
        return None
    for k, mo in RU.items():
        if k in s:
            return date(int(y.group()), mo, 1)
    return None


def _num(v):
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _get_sku(conn, name, cache):
    if name in cache:
        return cache[name]
    row = conn.execute(text("SELECT sku_id FROM core.dim_sku WHERE name=:n"), {"n": name}).fetchone()
    sid = row[0] if row else conn.execute(
        text("INSERT INTO core.dim_sku(name) VALUES(:n) RETURNING sku_id"), {"n": name}).scalar_one()
    cache[name] = sid
    return sid


def main():
    df = pd.read_excel(FILE, header=None, dtype=str).fillna("")
    row0 = df.iloc[0].tolist()
    # блок месяца = 4 колонки: [Количество, Выручка, Рентабельность%, Себестоимость]
    mcols = []  # (qty_col, rub_col, cost_col, month)
    for j in range(1, len(row0)):
        m = _mon(row0[j])
        if m:
            mcols.append((j, j + 1, j + 3, m))
    print(f"месяцев: {len(mcols)}, строк: {df.shape[0]}")

    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM core.fact_sellin WHERE source_file=:f"), {"f": SRC})
        cur_buyer, clis, skus, n = None, {}, {}, 0
        for r in range(4, df.shape[0]):
            label = str(df.iloc[r, 0]).strip()
            if not label:
                continue
            low = label.lower()
            if "livs" in low or "ливс" in low:
                if cur_buyer is None:
                    continue
                cid = clis.get(cur_buyer) or clis.setdefault(cur_buyer, get_or_create_client(conn, cur_buyer))
                sid = _get_sku(conn, label, skus)
                batch = []
                for qc, rc, cc, mon in mcols:
                    qty = _num(df.iloc[r, qc])
                    if not qty:
                        continue
                    batch.append({"c": cid, "s": sid, "p": mon, "q": qty,
                                  "r": _num(df.iloc[r, rc]), "cost": _num(df.iloc[r, cc]), "f": SRC})
                if batch:
                    conn.execute(text("INSERT INTO core.fact_sellin(client_id,sku_id,period,qty,rub,cost_rub,source_file) "
                                      "VALUES(:c,:s,:p,:q,:r,:cost,:f)"), batch)
                    n += len(batch)
            elif LEGAL.search(low):
                cur_buyer = label
    print(f"fact_sellin строк: {n} | покупателей: {len(clis)} | товаров: {len(skus)}")


if __name__ == "__main__":
    main()
