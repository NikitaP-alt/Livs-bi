"""Социальная аптека (Фармацевт). 3 файла, тип факта — по имени файла:
- продажи            -> sellout      (кол-во «Продажи упаковки», точка «Аптека Краткое…»)
- остатки (Неликвид) -> stock        (кол-во «Состояние склада упаковки», точка «Контрагент Краткое…»)
- закупки со склада  -> pos_purchase (кол-во «Закупки упаковки», точка «Аптека Краткое…»)

Товар — «Наименование товара». Колонки ищем по названиям (устойчиво к перестановкам). Период — из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Социальная аптека"


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


def _find(cols, *keys) -> Optional[int]:
    for j, c in enumerate(cols):
        cl = str(c).strip().lower()
        if all(k in cl for k in keys):
            return j
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    month = _month(period_override)
    nl = str(file_path).lower()
    if "закуп" in nl:
        src = "pos_purchase"
    elif "остат" in nl:
        src = "stock"
    else:
        src = "sellout"

    df = pd.read_excel(file_path, sheet_name=0, header=None, dtype=str, engine="openpyxl").fillna("")
    cols = [str(x).strip() for x in df.iloc[0].tolist()]
    jname = _find(cols, "наименование", "товар")

    if src == "pos_purchase":
        jqty, jrub = _find(cols, "закупки", "упаковки"), _find(cols, "закупки", "цен")
        jtt, jinn = _find(cols, "аптека", "крат"), _find(cols, "аптека", "инн")
    elif src == "stock":
        jqty, jrub = _find(cols, "состояние склада", "упаковки"), _find(cols, "состояние склада", "цен")
        jtt, jinn = _find(cols, "контрагент", "крат"), _find(cols, "контрагент", "инн")
    else:
        jqty, jrub = _find(cols, "продажи", "упаковки"), _find(cols, "продажи", "сип")
        jtt, jinn = _find(cols, "аптека", "крат"), _find(cols, "аптека", "инн")

    rows: list[SalesRow] = []
    for i in range(1, df.shape[0]):
        name = str(df.iloc[i, jname]).strip() if jname is not None else ""
        if not name or name.lower().startswith(("итог", "общий")):
            continue
        qty = _num(df.iloc[i, jqty]) if jqty is not None else 0.0
        if qty <= 0:
            continue
        rub = _num(df.iloc[i, jrub]) if jrub is not None else 0.0
        tt = str(df.iloc[i, jtt]).strip() if jtt is not None else ""
        inn = str(df.iloc[i, jinn]).strip() if jinn is not None else ""
        r = SalesRow(source=src, client_name=CLIENT, sku_code=name, sku_name=name, qty=qty,
                     rub=(rub or None), tt_code=(tt or None), tt_name=(tt or None),
                     tt_inn=(inn or None))
        if src == "stock":
            r.snapshot_date = _eom(month) if month else None
        else:
            r.period = month
        rows.append(r)
    return rows, []
