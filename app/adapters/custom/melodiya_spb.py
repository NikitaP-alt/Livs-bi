"""Переходник: Мелодия Здоровья (СПБ). Пивот-выгрузка.
Листы: «поставка» (закуп) и «продажа» (продажи). Колонка 0 = товар «…[LIVS]», колонка 1 = кол-во.
Период — из имени/пути (батч передаёт period_override)."""
from __future__ import annotations
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Мелодия Здоровья (СПБ)"


def _num(v) -> Optional[float]:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _livs(n: str) -> bool:
    n = n.lower()
    return "livs" in n or "ливс" in n


def adapt(file_path, period_override: Optional[str] = None):
    month = None
    if period_override:
        d = datetime.strptime(period_override + "-01", "%Y-%m-%d").date()
        month = date(d.year, d.month, 1)
    if month is None:
        raise ValueError("Мелодия СПб: нужен период (из имени файла)")

    xl = pd.ExcelFile(file_path)
    rows: list[SalesRow] = []
    raw: list[dict] = []
    for sheet in xl.sheet_names:
        sl = sheet.lower()
        if "поставк" in sl or "закуп" in sl:
            src = "pos_purchase"
        elif "продаж" in sl or "реализ" in sl:
            src = "sellout"
        else:
            continue
        df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str).fillna("")
        if df.shape[1] < 2:
            continue
        for r in df.itertuples(index=False):
            name = str(r[0]).strip()
            if not _livs(name) or any(t in name.lower() for t in ("итог", "всего", "total")):
                continue
            qty = _num(r[1])
            if not qty:
                continue
            raw.append({"_лист": sheet, "товар": name, "кол-во": qty})
            rows.append(SalesRow(source=src, client_name=CLIENT, sku_code=name, sku_name=name,
                                 qty=qty, period=month))
    return rows, raw
