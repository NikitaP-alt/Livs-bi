"""Переходник: Алоэ (Эндифарм). Выгрузки 1С, листы среди {закуп, продажи, остаток}.

- закуп:   длинная таблица Номенклатура | Контрагент | Аптека | Итого  -> pos_purchase (по аптеке).
- продажи: широкий пивот товар×аптека (коды аптек «0008-78 (СПб…)»)   -> sellout  (unpivot).
- остаток: широкий пивот товар×аптека                                 -> stock    (unpivot).

Период берём из ячейки «Период: DD.MM.YYYY» в шапке листа (fallback — --period).
Один файл может нести и один лист (продажи_04.26), и все три (Ливс отчет МАЙ 2026).
"""
from __future__ import annotations
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Алоэ (Эндифарм)"


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _period_from_sheet(df) -> Optional[date]:
    for i in range(min(6, df.shape[0])):
        for v in df.iloc[i].tolist():
            m = re.search(r"(\d{2})\.(\d{2})\.(20\d{2})", str(v))
            if m:
                return date(int(m.group(3)), int(m.group(2)), 1)
    return None


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _header_row(df, need_col1: bool) -> Optional[int]:
    """строка, где col0 == 'Номенклатура' (и col1 непустой, если need_col1)."""
    for i in range(df.shape[0]):
        if str(df.iloc[i, 0]).strip() == "Номенклатура":
            if not need_col1 or str(df.iloc[i, 1]).strip():
                return i
    return None


def _city(pharm: str) -> Optional[str]:
    m = re.search(r"\(([^,)]+)", pharm)
    return m.group(1).strip() if m else None


def _adapt_sheet(df, sheet: str, fallback: Optional[date]):
    rows: list[SalesRow] = []
    period = _period_from_sheet(df) or fallback
    low = sheet.lower()

    if "закуп" in low:                                     # длинная: товар·контрагент·аптека·кол-во
        h = _header_row(df, need_col1=False)
        if h is None:
            return rows
        for i in range(h + 1, df.shape[0]):
            name = str(df.iloc[i, 0]).strip()
            if not name or name.lower().startswith(("итог", "общий")):
                continue
            pharm = str(df.iloc[i, 2]).strip()
            if not pharm:                       # строки-итоги (без аптеки) пропускаем
                continue
            qty = _num(df.iloc[i, 3]) if df.shape[1] > 3 else 0.0
            if qty <= 0:
                continue
            contr = str(df.iloc[i, 1]).strip() or None
            rows.append(SalesRow(source="pos_purchase", client_name=CLIENT,
                                 sku_code=name, sku_name=name, qty=qty,
                                 tt_code=(pharm or name), tt_name=(pharm or None),
                                 tt_chain=contr, tt_city=(_city(pharm) if pharm else None),
                                 period=period))
        return rows

    # продажи / остаток — широкий пивот товар×аптека
    src = "sellout" if "продаж" in low else "stock"
    h = _header_row(df, need_col1=True)
    if h is None:
        return rows
    pharm = {j: str(df.iloc[h, j]).strip() for j in range(1, df.shape[1])
             if str(df.iloc[h, j]).strip() and "итог" not in str(df.iloc[h, j]).strip().lower()}
    for i in range(h + 1, df.shape[0]):
        name = str(df.iloc[i, 0]).strip()
        if not name or name.lower().startswith(("общий итог", "итог")):
            continue
        for j, ph in pharm.items():
            v = _num(df.iloc[i, j])
            if v <= 0:
                continue
            r = SalesRow(source=src, client_name=CLIENT, sku_code=name, sku_name=name, qty=v,
                         tt_code=ph, tt_name=ph, tt_city=_city(ph))
            if src == "sellout":
                r.period = period
            else:
                r.snapshot_date = _eom(period) if period else None
            rows.append(r)
    return rows


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    fallback = None
    if period_override:
        d = datetime.strptime(period_override[:7] + "-01", "%Y-%m-%d").date()
        fallback = date(d.year, d.month, 1)
    xl = pd.ExcelFile(file_path, engine="openpyxl")
    all_rows: list[SalesRow] = []
    for sh in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sh, header=None, dtype=str,
                           engine="openpyxl").fillna("")
        if df.shape[0] < 2:
            continue
        all_rows += _adapt_sheet(df, sh, fallback)
    return all_rows, []
