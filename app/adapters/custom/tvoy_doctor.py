"""ТвойДоктор: один файл, 3 листа — Остатки / Продажи / Закупки.
Товар = Номенклатура, точка = Склад. Остатки->stock (Остаток), Продажи->sellout (Количество),
Закупки->pos_purchase (Количество). Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "ТвойДоктор"


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


def _find(cols, *keys) -> Optional[int]:
    for j, c in enumerate(cols):
        if all(k in str(c).strip().lower() for k in keys):
            return j
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    rows: list[SalesRow] = []
    for sh in xl.sheet_names:
        low = sh.lower()
        if "остат" in low:
            src = "stock"
        elif "закуп" in low:
            src = "pos_purchase"
        elif "продаж" in low:
            src = "sellout"
        else:
            continue
        df = pd.read_excel(file_path, sheet_name=sh, header=None, dtype=str,
                           engine="openpyxl").fillna("")
        if df.shape[0] < 2:
            continue
        cols = [str(x).strip() for x in df.iloc[0].tolist()]
        jname = _find(cols, "номенклатура")
        jsklad = _find(cols, "склад")
        jrub = _find(cols, "сумма закупки") or _find(cols, "стоимость")
        jqty = _find(cols, "остаток") if src == "stock" else _find(cols, "количество")
        for i in range(1, df.shape[0]):
            name = str(df.iloc[i, jname]).strip() if jname is not None else ""
            if not name or name.lower().startswith(("итог", "общий")):
                continue
            qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
            if qty <= 0:
                continue
            rub = _num(df.iloc[i, jrub]) if jrub is not None else 0.0
            tt = str(df.iloc[i, jsklad]).strip() if jsklad is not None else ""
            r = SalesRow(source=src, client_name=CLIENT, sku_code=name, sku_name=name, qty=qty,
                         rub=(rub or None), tt_code=(tt or None), tt_name=(tt or None))
            if src == "stock":
                r.snapshot_date = _eom(month) if month else None
            else:
                r.period = month
            rows.append(r)
    return rows, []
