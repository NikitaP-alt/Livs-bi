"""Фармакопейка (Медэкспорт): файлы закуп/остатки/продажи. Шапка на строке с «Аналог»:
ГодМесяц | Организация | КодАналога | Аналог | Приход/Расход/Остаток, уп.
Тип факта — по имени файла (закуп->pos_purchase, остат->stock, продаж/расход->sellout).
Товар = Аналог (код = КодАналога). Точек нет (агрегат сети). Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Фармакопейка (Омск) Медэкспорт"


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
    nl = str(file_path).lower()
    if "закуп" in nl or "приход" in nl:
        src = "pos_purchase"
    elif "остат" in nl:
        src = "stock"
    else:
        src = "sellout"
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    hdr = next((i for i in range(min(6, df.shape[0]))
                if any("аналог" == str(x).strip().lower() for x in df.iloc[i].tolist())), None)
    if hdr is None:
        return [], []
    cols = [str(x).strip().lower() for x in df.iloc[hdr].tolist()]
    jname = next((j for j, c in enumerate(cols) if c == "аналог"), None)
    jcode = next((j for j, c in enumerate(cols) if "коданалог" in c or c == "код"), None)
    jqty = next((j for j, c in enumerate(cols) if "уп" in c and any(k in c for k in ("приход", "расход", "остаток"))), None)
    if jqty is None:
        jqty = max((j for j, c in enumerate(cols) if c), default=None)   # последняя колонка = кол-во
    rows: list[SalesRow] = []
    for i in range(hdr + 1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий")):
            continue
        qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
        if qty <= 0:
            continue
        code = str(df.iloc[i, jcode]).strip() if jcode is not None else ""
        r = SalesRow(source=src, client_name=CLIENT, sku_code=(code or name), sku_name=name, qty=qty)
        if src == "stock":
            r.snapshot_date = _eom(month) if month else None
        else:
            r.period = month
        rows.append(r)
    return rows, []
