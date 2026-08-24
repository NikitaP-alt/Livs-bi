"""Эркафарм: один файл, строка = SKU × аптека, сразу продажи + остаток + закуп.
«Продажи, шт»->sellout · «ТЗ на конец месяца, шт»->stock · «Закупки, шт»->pos_purchase.
Товар=SKU Наименование, точка=Торговая точка, ИНН=ИНН аптеки. Период — из колонки «Дата» (или --period).
Файл «…акции…» (отчёт по скидкам) — не грузим.
"""
from __future__ import annotations
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Эркафарм"


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


def _month(cell, override) -> Optional[date]:
    m = re.search(r"(20\d{2})[.\-/](\d{2})", str(cell))
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
    if "акци" in str(file_path).lower():                    # отчёт по скидкам — не факт продаж
        return [], []
    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    cols = [str(x).strip() for x in df.iloc[0].tolist()]
    jname = _find(cols, "sku", "наимен") or _find(cols, "наимен")
    jtt = _find(cols, "торговая точка")
    jinn = _find(cols, "инн", "аптек")
    jdate = _find(cols, "дата")
    j_so, j_so_rub = _find(cols, "продажи", "шт"), _find(cols, "продажи", "зц")
    j_st, j_st_rub = _find(cols, "тз на конец", "шт"), _find(cols, "тз на конец", "зц")
    j_zk, j_zk_rub = _find(cols, "закупки", "шт"), _find(cols, "закупки", "зц", exclude=("средн",))

    rows: list[SalesRow] = []
    for i in range(1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий")):
            continue
        per = _month(df.iloc[i, jdate] if jdate is not None else "", period_override)
        tt = str(df.iloc[i, jtt]).strip() if jtt is not None else ""
        inn = str(df.iloc[i, jinn]).strip() if jinn is not None else ""
        common = dict(client_name=CLIENT, sku_code=name, sku_name=name,
                      tt_code=(tt or None), tt_name=(tt or None), tt_inn=(inn or None))
        q = _num(df.iloc[i, j_so]) if j_so is not None else 0.0
        if q > 0:
            rows.append(SalesRow(source="sellout", qty=q,
                                 rub=(_num(df.iloc[i, j_so_rub]) or None) if j_so_rub is not None else None,
                                 period=per, **common))
        q = _num(df.iloc[i, j_st]) if j_st is not None else 0.0
        if q > 0 and per:
            rows.append(SalesRow(source="stock", qty=q,
                                 rub=(_num(df.iloc[i, j_st_rub]) or None) if j_st_rub is not None else None,
                                 snapshot_date=_eom(per), **common))
        q = _num(df.iloc[i, j_zk]) if j_zk is not None else 0.0
        if q > 0:
            rows.append(SalesRow(source="pos_purchase", qty=q,
                                 rub=(_num(df.iloc[i, j_zk_rub]) or None) if j_zk_rub is not None else None,
                                 period=per, **common))
    return rows, []
