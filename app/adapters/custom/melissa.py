"""Мелисса (Гранд Фарм): блоки по магазинам. Строка-магазин: col0 пусто, col1 = название магазина.
Ниже товары: Код товара | Наименование | продано | остаток. Даёт продажи(продано)+остатки(остаток)
на магазин×товар. Строки-разделы («Реализация и остатки склада…») пропускаем. Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Мелисса (Гранд Фарм) Новосибирск"


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _month(o: Optional[str]) -> Optional[date]:
    if not o:
        return None
    d = datetime.strptime(o[:7] + "-01", "%Y-%m-%d").date()
    return date(d.year, d.month, 1)


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    # шапка: col0='Код товара', col2='продано', col3='остаток'
    hdr = next((i for i in range(min(4, df.shape[0]))
                if "код товара" in str(df.iloc[i, 0]).strip().lower()), 0)
    rows: list[SalesRow] = []
    store = None
    for i in range(hdr + 1, df.shape[0]):
        c0 = str(df.iloc[i, 0]).strip()
        c1 = str(df.iloc[i, 1]).strip()
        if not c0 and c1:                                   # строка-магазин (или раздел)
            store = None if ("реализац" in c1.lower() or "остатк" in c1.lower()) else c1
            continue
        if not c0 or store is None:                         # не товар / вне магазина
            continue
        name = c1 or c0
        sold = _num(df.iloc[i, 2])
        stock = _num(df.iloc[i, 3])
        if sold > 0:
            rows.append(SalesRow(source="sellout", client_name=CLIENT, sku_code=c0, sku_name=name,
                                 qty=sold, tt_code=store, tt_name=store, period=month))
        if stock > 0:
            rows.append(SalesRow(source="stock", client_name=CLIENT, sku_code=c0, sku_name=name,
                                 qty=stock, tt_code=store, tt_name=store,
                                 snapshot_date=_eom(month) if month else None))
    return rows, []
