"""Переходник: РКМ. Длинная таблица продаж (строка = продажа):
Код товара | Название товара | Количество | Адрес аптеки [| Аптека | Фирма-производитель].
Лист «Озон» (ФИО|Кол-во|Сертификаты) — промо/сотрудники, пропускаем.
Период в файле отсутствует -> берём из --period (YYYY-MM).
"""
from __future__ import annotations
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
        jqty = _find(hdr, "количество", "кол-во", "кол - во")
        if jcode is None or jqty is None:               # лист «Озон»/пустой — пропускаем
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
