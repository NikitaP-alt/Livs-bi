"""Переходник: РКМ. Два формата:
1) СТАРЫЙ (2026 Q2): длинная таблица продаж — Код товара | Название | Количество | Адрес аптеки.
2) НОВЫЙ (июль'26): Аптека | Код товара | Товар | Производитель | Продажи Кол-во | Остатки Кол-во
   -> sellout (Продажи Кол-во) + stock (Остатки Кол-во).
Лист «Озон» (промо) пропускаем. Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "РКМ"


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _month(override: Optional[str]) -> Optional[date]:
    if not override:
        return None
    d = datetime.strptime(override[:7] + "-01", "%Y-%m-%d").date()
    return date(d.year, d.month, 1)


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _find(hdr, *keys) -> Optional[int]:
    for j, h in enumerate(hdr):
        if any(k in str(h).strip().lower() for k in keys):
            return j
    return None


def _find_exact(hdr, val) -> Optional[int]:
    for j, h in enumerate(hdr):
        if str(h).strip().lower() == val:
            return j
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    rows: list[SalesRow] = []
    for sh in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sh, header=None, dtype=str,
                           engine="openpyxl").fillna("")
        if df.shape[0] < 2:
            continue
        hdr = [str(x).strip() for x in df.iloc[0].tolist()]
        jcode = _find(hdr, "код товара", "код")
        if jcode is None:                                   # лист «Озон»/пустой
            continue
        j_prod, j_ost = _find(hdr, "продажи"), _find(hdr, "остатки")

        if j_prod is not None and j_ost is not None:        # НОВЫЙ формат (продажи + остатки)
            jtovar = _find_exact(hdr, "товар")
            japt = _find_exact(hdr, "аптека")
            if japt is None:
                japt = _find(hdr, "адрес")
            for i in range(1, df.shape[0]):
                code = str(df.iloc[i, jcode]).strip()
                if not code or code.lower().startswith(("итог", "общий")):
                    continue
                name = str(df.iloc[i, jtovar]).strip() if jtovar is not None else ""
                tt = str(df.iloc[i, japt]).strip() if japt is not None else ""
                common = dict(client_name=CLIENT, sku_code=code, sku_name=(name or code),
                              tt_code=(tt or None), tt_name=(tt or None))
                sold = _num(df.iloc[i, j_prod])
                if sold > 0:
                    rows.append(SalesRow(source="sellout", qty=sold, period=month, **common))
                stock = _num(df.iloc[i, j_ost])
                if stock > 0:
                    rows.append(SalesRow(source="stock", qty=stock,
                                         snapshot_date=_eom(month) if month else None, **common))
            continue

        jqty = _find(hdr, "количество", "кол-во", "кол - во")   # СТАРЫЙ формат
        if jqty is None:
            continue
        jname = _find(hdr, "название", "наименование")
        jaddr = _find(hdr, "адрес")
        jph = _find_exact(hdr, "аптека")
        for i in range(1, df.shape[0]):
            code = str(df.iloc[i, jcode]).strip()
            if not code or code.lower().startswith(("итог", "общий")):
                continue
            qty = _num(df.iloc[i, jqty])
            if qty <= 0:
                continue
            name = str(df.iloc[i, jname]).strip() if jname is not None else ""
            addr = str(df.iloc[i, jaddr]).strip() if jaddr is not None else ""
            phname = str(df.iloc[i, jph]).strip() if jph is not None else ""
            rows.append(SalesRow(source="sellout", client_name=CLIENT,
                                 sku_code=code, sku_name=(name or code), qty=qty,
                                 tt_code=(addr or phname or None),
                                 tt_name=(phname or addr or None), period=month))
    return rows, []
