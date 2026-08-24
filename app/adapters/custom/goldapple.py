"""Золотое яблоко: отчёт по продажам (лист LIVS). Строка = продажа в магазине.
Колонки: Дата·Месяц·Страна·Магазин·Товар·Код товара·Штрихкод·Артикул·Выручка…·Количество продаж.
Первая строка после шапки — итоги (Товар пуст) — пропускаем. Период — из колонки «Месяц».
"""
from __future__ import annotations
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Золотое яблоко"


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _find(cols, *keys, exclude=()) -> Optional[int]:
    for j, c in enumerate(cols):
        cl = str(c).strip().lower()
        if all(k in cl for k in keys) and not any(x in cl for x in exclude):
            return j
    return None


def _month(cell, override) -> Optional[date]:
    m = re.search(r"(20\d{2})[.\-/](\d{2})", str(cell))
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    if override:
        d = datetime.strptime(override[:7] + "-01", "%Y-%m-%d").date()
        return date(d.year, d.month, 1)
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    cols = [str(x).strip() for x in df.iloc[0].tolist()]
    jname = _find(cols, "товар", exclude=("код",))          # «Товар», не «Код товара»
    jart = _find(cols, "артикул")
    jshop = _find(cols, "магазин")
    jqty = _find(cols, "количество прод")
    jrub = _find(cols, "выручка", "касс")
    jmon = _find(cols, "месяц")

    rows: list[SalesRow] = []
    for i in range(1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий")):
            continue                                        # строка-итоги (Товар пуст) / тоталы
        qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
        if qty <= 0:
            continue
        art = str(df.iloc[i, jart]).strip() if jart is not None else ""
        shop = str(df.iloc[i, jshop]).strip() if jshop is not None else ""
        rub = _num(df.iloc[i, jrub]) if jrub is not None else 0.0
        per = _month(df.iloc[i, jmon] if jmon is not None else "", period_override)
        rows.append(SalesRow(source="sellout", client_name=CLIENT,
                             sku_code=(art or name), sku_name=name, qty=qty,
                             rub=(rub or None), tt_code=(shop or None), tt_name=(shop or None),
                             period=per))
    return rows, []
