"""ОАС: файл «Отчет о продажах <месяц> 2026.xlsx», 2 листа:
- «закуп»:   Коммерческое наименование | Контрагенты | <месяц>(кол-во)  -> pos_purchase
- «продажи»: Склады | Коммерческое наименование | Оборот шт | Текущий остаток
             -> sellout (Оборот шт) + stock (Текущий остаток)
Товар — по коммерческому наименованию. Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "ОАС"


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


def _hdr(df, kw):
    for i in range(min(8, df.shape[0])):
        if any(kw in str(x).strip().lower() for x in df.iloc[i].tolist()):
            return i
    return None


def _find(row, *keys):
    for j, c in enumerate(row):
        if all(k in str(c).strip().lower() for k in keys):
            return j
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    rows: list[SalesRow] = []
    for sh in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sh, header=None, dtype=str,
                           engine="openpyxl").fillna("")
        h = _hdr(df, "коммерческ")
        if h is None:
            continue
        hdr = [str(x).strip() for x in df.iloc[h].tolist()]
        jname = _find(hdr, "коммерческ")
        low = sh.lower()
        if "закуп" in low:                                  # длинная: наим | контрагент | кол-во
            jqty = max((j for j, c in enumerate(hdr) if str(c).strip()), default=None)
            for i in range(h + 1, df.shape[0]):
                name = str(df.iloc[i, jname]).strip()
                if not name or name.lower().startswith(("итог", "общий")):
                    continue
                qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
                if qty <= 0:
                    continue
                rows.append(SalesRow(source="pos_purchase", client_name=CLIENT,
                                     sku_code=name, sku_name=name, qty=qty, period=month))
        else:                                               # продажи: склад | наим | оборот шт | тек.остаток
            jtt = _find(hdr, "склад")
            jso = _find(hdr, "оборот")
            jst = _find(hdr, "остаток")
            for i in range(h + 1, df.shape[0]):
                name = str(df.iloc[i, jname]).strip()
                if not name or name.lower().startswith(("итог", "общий")):
                    continue
                tt = str(df.iloc[i, jtt]).strip() if jtt is not None else ""
                qso = _num(df.iloc[i, jso]) if jso is not None else 0.0
                if qso > 0:
                    rows.append(SalesRow(source="sellout", client_name=CLIENT, sku_code=name,
                                         sku_name=name, qty=qso, tt_code=(tt or None),
                                         tt_name=(tt or None), period=month))
                qst = _num(df.iloc[i, jst]) if jst is not None else 0.0
                if qst > 0:
                    rows.append(SalesRow(source="stock", client_name=CLIENT, sku_code=name,
                                         sku_name=name, qty=qst, tt_code=(tt or None),
                                         tt_name=(tt or None), snapshot_date=_eom(month) if month else None))
    return rows, []
