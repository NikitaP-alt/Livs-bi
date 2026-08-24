"""Невис: лист TDSheet (шапка не на 1-й строке — ищем по «Номенклатура»).
- продажи: Номер аптеки | Адрес | Номенклатура | Количество            -> sellout
- остатки: …Номенклатура… | Адрес | … | Количество Остаток            -> stock
Тип факта — по имени файла (остат -> stock, иначе sellout). Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Невис"


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
    src = "stock" if "остат" in str(file_path).lower() else "sellout"
    sheet = "TDSheet"
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    if sheet not in xl.sheet_names:
        sheet = 0
    df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str, engine="openpyxl").fillna("")
    # шапка = строка, где есть колонка «Номенклатура»
    hdr = next((i for i in range(min(12, df.shape[0]))
                if any(str(x).strip().lower() == "номенклатура" for x in df.iloc[i].tolist())), None)
    if hdr is None:
        return [], []
    cols = [str(x).strip().lower() for x in df.iloc[hdr].tolist()]

    def find(*keys):
        for j, c in enumerate(cols):
            if all(k in c for k in keys):
                return j
        return None

    jname = next((j for j, c in enumerate(cols) if c == "номенклатура"), None)
    jaddr = find("адрес")
    japt = find("номер аптеки")
    jqty = find("количество", "остат") if src == "stock" else find("количество")
    if jqty is None:
        jqty = find("количество")
    rows: list[SalesRow] = []
    for i in range(hdr + 1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий", "всего")):
            continue
        qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
        if qty <= 0:
            continue
        addr = str(df.iloc[i, jaddr]).strip() if jaddr is not None else ""
        apt = str(df.iloc[i, japt]).strip() if japt is not None else ""
        r = SalesRow(source=src, client_name=CLIENT, sku_code=name, sku_name=name, qty=qty,
                     tt_code=(addr or apt or None), tt_name=(addr or None))
        if src == "stock":
            r.snapshot_date = _eom(month) if month else None
        else:
            r.period = month
        rows.append(r)
    return rows, []
