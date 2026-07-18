"""Ригла: СТМ ЛИВС под маркой «АВС хэлси фуд». Широкая матрица товар × месяцы:
строка 0 — метки месяцев (2023/Март…), строка-шапка — «Код АП | Названия строк | Продажи, уп | Кол-во аптек | …».
Разворачиваем «Продажи, уп» по месяцам (колонки «Кол-во аптек» и группу ИТОГО пропускаем). Бренд-фильтр не нужен (весь файл = ЛИВС)."""
from __future__ import annotations
import re
from datetime import date
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Ригла"
RU = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6, "июль": 7,
      "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12}


def _num(v) -> Optional[float]:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _mon(s: str) -> Optional[date]:
    y = re.search(r"(20\d{2})", s or "")
    if not y:
        return None
    for w, mo in RU.items():
        if w in (s or "").lower():
            return date(int(y.group(1)), mo, 1)
    return None


def adapt(file_path, period_override: Optional[str] = None):
    xl = pd.ExcelFile(file_path)
    rows: list[SalesRow] = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str).fillna("")
        hidx = None
        for i in range(min(8, len(df))):
            vals = [str(x).strip().lower() for x in df.iloc[i].tolist()]
            if any("названия строк" in v or "код ап" in v for v in vals):
                hidx = i
                break
        if hidx is None:
            continue
        hdr = [str(x).strip() for x in df.iloc[hidx].tolist()]
        monthrow = [str(x).strip() for x in df.iloc[hidx - 1].tolist()] if hidx > 0 else [""] * len(hdr)
        namecol = next((j for j, h in enumerate(hdr) if "названия строк" in h.lower()), 1)

        salecols = []
        curmon = ""
        for j, h in enumerate(hdr):
            if j < len(monthrow) and monthrow[j]:
                curmon = monthrow[j]
            if "продаж" in h.lower() and "итог" not in curmon.lower():
                mon = _mon(curmon)
                if mon:
                    salecols.append((j, mon))

        for r in range(hidx + 1, len(df)):
            name = str(df.iloc[r, namecol]).strip()
            if not name or name.lower() in ("мр", "итого") or "итог" in name.lower():
                continue
            for j, mon in salecols:
                qty = _num(df.iloc[r, j])
                if not qty:
                    continue
                rows.append(SalesRow(source="sellout", client_name=CLIENT,
                                     sku_code=name, sku_name=name, qty=qty, period=mon))
    return rows, []
