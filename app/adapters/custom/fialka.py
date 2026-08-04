"""Переходник: Фиалка (СПб). Широкий пивот: строки = товары, колонки = аптеки (улицы СПб:
ДЫБЕНКО, ЛЕНИНСКИЙ 88, ЭНГЕЛЬСА 126/1 …). Подпись «Оборот шт» -> sellout, «Приход шт» -> pos_purchase.
Строку «Общий итог» и колонки-итоги пропускаем. Период — из --period (в файле его нет).
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Фиалка"
CITY = "Санкт-Петербург"


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


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str,
                       engine="openpyxl").fillna("")
    rows: list[SalesRow] = []

    # строка с 'Наименование' в col0: под ней товары, аптеки — строкой ВЫШЕ
    hrow = next((i for i in range(df.shape[0])
                 if str(df.iloc[i, 0]).strip() == "Наименование"), None)
    if hrow is None or hrow == 0:
        return rows, []

    sub = " ".join(str(x).strip().lower() for x in df.iloc[hrow].tolist())
    src = "pos_purchase" if "приход" in sub else "sellout"

    pharm = {j: str(df.iloc[hrow - 1, j]).strip()
             for j in range(1, df.shape[1])
             if str(df.iloc[hrow - 1, j]).strip()
             and "итог" not in str(df.iloc[hrow - 1, j]).strip().lower()}

    for i in range(hrow + 1, df.shape[0]):
        name = str(df.iloc[i, 0]).strip()
        if not name or name.lower().startswith(("общий итог", "итог")):
            continue
        for j, ph in pharm.items():
            v = _num(df.iloc[i, j])
            if v <= 0:
                continue
            rows.append(SalesRow(source=src, client_name=CLIENT, sku_code=name,
                                 sku_name=name, qty=v, tt_code=ph, tt_name=ph,
                                 tt_city=CITY, period=month))
    return rows, []
