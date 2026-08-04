"""Фармперспектива (битый xlsx — чиним регистр sharedStrings). Три формата:
1) ЗАКУП — иерархия «Поставщик/Товар | Количество» (имя товара = самая правая непустая ячейка).
2) ОСТАТКИ/ПРОДАЖИ — широкая матрица: строка-шапка «Розничная точка | товар1 | товар2 | … | Итог»,
   строки = адреса точек, в ячейках кол-во. Разворачиваем.
Весь файл = ЛИВС (бренд-фильтр не нужен). Период — из имени/папки."""
from __future__ import annotations
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow
from ..auto import _fix_xlsx

CLIENT = "Фармперспектива"


def _num(v) -> Optional[float]:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _month(period_override, name) -> Optional[date]:
    if period_override:
        d = datetime.strptime(period_override + "-01", "%Y-%m-%d").date()
        return date(d.year, d.month, 1)
    m = re.search(r"(\d{2})\.(\d{2})\.(20\d{2})", name)
    return date(int(m.group(3)), int(m.group(2)), 1) if m else None


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _row_with(df, kw, lim=10):
    for i in range(min(len(df), lim)):
        for x in df.iloc[i].tolist():
            if kw in str(x).lower():
                return i
    return None


FP_MONTHS = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
             "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12}


def _sheet_period(sheet: str) -> Optional[date]:
    """Период из имени листа: 'май_26' -> 2026-05. Листы без года (2025) -> None (пропуск)."""
    s = sheet.lower().replace("_", "").replace(" ", "")
    for w, mo in FP_MONTHS.items():
        if s.startswith(w):
            yy = re.search(r"(\d{2})", s[len(w):])
            return date(2000 + int(yy.group(1)), mo, 1) if yy else None
    return None


def _adapt_pomesyachno(fp):
    """Накопительный файл «отчеты помесячно»: каждый лист = месяц (продажи по товару).
    Разметка листов разная — ищем товарную колонку и кол-во/сумму по ключам. Берём только 2026."""
    xl = pd.ExcelFile(fp)
    rows: list[SalesRow] = []
    for sheet in xl.sheet_names:
        per = _sheet_period(sheet)
        if per is None or per.year < 2026:
            continue
        df = pd.read_excel(fp, sheet_name=sheet, header=None, dtype=str).fillna("")
        hr = pcol = None
        for i in range(min(6, len(df))):
            for j in range(df.shape[1]):
                cl = str(df.iloc[i, j]).strip().lower()
                if cl and ("птовар" in cl or cl == "товар" or "наимен" in cl) and "код" not in cl:
                    hr, pcol = i, j
                    break
            if hr is not None:
                break
        if hr is None:
            continue
        lbl = {j: (str(df.iloc[hr, j]) + " " + (str(df.iloc[hr + 1, j]) if hr + 1 < len(df) else "")).lower()
               for j in range(df.shape[1])}
        qcol = next((j for j, l in lbl.items()
                     if j != pcol and ("продано" in l or "кол-во" in l or "количество" in l)), None)
        rcol = next((j for j, l in lbl.items()
                     if j not in (pcol, qcol) and ("сумма" in l or "руб" in l)), None)
        if rcol is None:                                   # формат B: второй столбец «Продано» = руб
            rcol = next((j for j, l in lbl.items() if j not in (pcol, qcol) and "продано" in l), None)
        if qcol is None:
            continue
        for r in range(hr + 1, len(df)):
            name = str(df.iloc[r, pcol]).strip()
            if not name or name.lower().startswith(("ливс", "итог", "общий")):
                continue
            qty = _num(df.iloc[r, qcol])
            if qty is None or qty <= 0:
                continue
            rub = _num(df.iloc[r, rcol]) if rcol is not None else None
            rows.append(SalesRow(source="sellout", client_name=CLIENT, sku_code=name,
                                 sku_name=name, qty=qty, rub=rub, period=per))
    return rows, []


def adapt(file_path, period_override: Optional[str] = None):
    fp = _fix_xlsx(str(file_path))
    name = Path(file_path).name
    nlow = name.lower()
    if "помесячно" in nlow:                         # накопительный файл с листами-месяцами
        return _adapt_pomesyachno(fp)
    month = _month(period_override, name)
    src_wide = "stock" if "остат" in nlow else ("sellout" if ("продаж" in nlow or "реализ" in nlow) else None)
    xl = pd.ExcelFile(fp)
    rows: list[SalesRow] = []

    for sheet in xl.sheet_names:
        df = pd.read_excel(fp, sheet_name=sheet, header=None, dtype=str).fillna("")

        # --- ЗАКУП (иерархия) ---
        hq = _row_with(df, "количество")
        if hq is not None:
            hdr = [str(x).strip().lower() for x in df.iloc[hq].tolist()]
            qcol = next((j for j, h in enumerate(hdr) if "количество" in h), None)
            if qcol is None or month is None:
                continue
            for r in range(hq + 1, len(df)):
                label = [str(df.iloc[r, c]).strip() for c in range(qcol)]
                nm = next((v for v in reversed(label) if v), "")
                qty = _num(df.iloc[r, qcol])
                if not nm or qty is None or qty == 0:
                    continue
                if any(x in nm.lower() for x in ("итог", "поставщик", "ооо", "оао", "зао", " ип ")):
                    continue
                rows.append(SalesRow(source="pos_purchase", client_name=CLIENT,
                                     sku_code=nm, sku_name=nm, qty=qty, period=month))
            continue

        # --- ОСТАТКИ/ПРОДАЖИ (широкая матрица) ---
        hw = _row_with(df, "розничная точк")
        if hw is not None and src_wide and month is not None:
            hdr = [str(x).strip() for x in df.iloc[hw].tolist()]
            ptcol = next((j for j, h in enumerate(hdr) if "розничная точк" in h.lower()), 0)
            prodcols = [(j, hdr[j]) for j in range(len(hdr))
                        if j != ptcol and hdr[j] and "итог" not in hdr[j].lower()]
            for r in range(hw + 1, len(df)):
                pt = str(df.iloc[r, ptcol]).strip()
                if not pt:
                    continue
                for j, pname in prodcols:
                    qty = _num(df.iloc[r, j])
                    if not qty:
                        continue
                    if src_wide == "stock":
                        rows.append(SalesRow(source="stock", client_name=CLIENT, sku_code=pname,
                                             sku_name=pname, qty=qty, tt_code=pt, tt_name=pt,
                                             snapshot_date=_eom(month)))
                    else:
                        rows.append(SalesRow(source="sellout", client_name=CLIENT, sku_code=pname,
                                             sku_name=pname, qty=qty, tt_code=pt, tt_name=pt, period=month))
            continue

    return rows, []
