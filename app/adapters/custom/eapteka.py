"""еАптека (новый формат 2026): один файл, строки по складам, сразу продажи + остатки + закуп.
Колонки: Месяц отчета · Адрес/Код склада · ИНН · Товар · Закупки шт/руб · Продажи шт · Выручка руб · Остаток шт.
Из каждой строки достаём до трёх фактов. Период — из «Месяц отчета» (или --period).
"""
from __future__ import annotations
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "еАптека"


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _month_from(cell, override: Optional[str]) -> Optional[date]:
    m = re.search(r"(20\d{2})[.\-](\d{2})", str(cell).strip())
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    if override:
        d = datetime.strptime(override[:7] + "-01", "%Y-%m-%d").date()
        return date(d.year, d.month, 1)
    return None


def _find(cols, *keys, exclude=()) -> Optional[int]:
    for j, c in enumerate(cols):
        cl = str(c).strip().lower()
        if all(k in cl for k in keys) and not any(x in cl for x in exclude):
            return j
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    cols = [str(x).strip() for x in df.iloc[0].tolist()]

    jmon = _find(cols, "месяц")
    jname = next((j for j, c in enumerate(cols) if c.strip().lower() == "товар"), None)
    if jname is None:
        jname = _find(cols, "наименование")
    jsklad = _find(cols, "адрес склада")
    jcode = _find(cols, "код склада")
    jinn = _find(cols, "инн")
    j_so = _find(cols, "продажи", "шт")
    j_so_rub = _find(cols, "выручка")
    j_st = _find(cols, "остаток", "шт")
    j_zk = _find(cols, "закупки", "шт")
    j_zk_rub = _find(cols, "закупки", "руб", exclude=("без",))   # «Закупки, руб.» (с НДС), не «БЕЗ НДС»

    rows: list[SalesRow] = []
    for i in range(1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий")):
            continue
        month = _month_from(df.iloc[i, jmon] if jmon is not None else "", period_override)
        tt = str(df.iloc[i, jsklad]).strip() if jsklad is not None else ""
        code = str(df.iloc[i, jcode]).strip() if jcode is not None else ""
        inn = str(df.iloc[i, jinn]).strip() if jinn is not None else ""
        common = dict(client_name=CLIENT, sku_code=name, sku_name=name,
                      tt_code=(code or tt or None), tt_name=(tt or None), tt_inn=(inn or None))

        q = _num(df.iloc[i, j_so]) if j_so is not None else 0.0
        if q > 0:
            rub = _num(df.iloc[i, j_so_rub]) if j_so_rub is not None else 0.0
            rows.append(SalesRow(source="sellout", qty=q, rub=(rub or None), period=month, **common))
        q = _num(df.iloc[i, j_st]) if j_st is not None else 0.0
        if q > 0 and month:
            rows.append(SalesRow(source="stock", qty=q, snapshot_date=_eom(month), **common))
        q = _num(df.iloc[i, j_zk]) if j_zk is not None else 0.0
        if q > 0:
            rub = _num(df.iloc[i, j_zk_rub]) if j_zk_rub is not None else 0.0
            rows.append(SalesRow(source="pos_purchase", qty=q, rub=(rub or None), period=month, **common))
    return rows, []
