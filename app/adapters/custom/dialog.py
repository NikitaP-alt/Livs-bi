"""Переходник: аптечная сеть «Диалог».

Два исторических формата (2022 и 2026), но колонки сопоставляются по ИМЕНАМ,
поэтому один код ловит оба:
- лист «Продажи»: Месяц, Аптека, Номенклатура, Кол-во (2026: «Количество», 2022: «Количество продаж»)
- лист «Остатки»: Аптека, Номенклатура, Кол-во (2026: «Количество», 2022: «Остаток»)
Листы «Сводная*», «ЕКом», «Оплата*» пропускаем.

Точка = «Аптека» (код вида ДС-Вернадского). Товар — по наименованию «Livs …».
Период: из колонки «Месяц» (дата 2026-05-01 ИЛИ текст «Декабрь 2022»); для остатков —
конец месяца отчёта. Несколько строк на (точка,товар) -> агрегируем СУММОЙ.
"""
from __future__ import annotations
import calendar
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Диалог"

RU_MONTHS = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
    "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s == "":
        return 0.0
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _parse_month_cell(val) -> Optional[date]:
    s = str(val).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    parts = s.split()
    if len(parts) >= 2 and parts[0].lower() in RU_MONTHS:
        try:
            return date(int(parts[-1]), RU_MONTHS[parts[0].lower()], 1)
        except ValueError:
            return None
    return None


def _month_from_name(name: str) -> Optional[date]:
    m = re.search(r"(\d{4})[.\-](\d{2})\b", name)          # 2026.05 / 2026-05
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    for word, mo in RU_MONTHS.items():                      # «Декабрь 2022»
        mm = re.search(word + r"\s+(\d{4})", name, re.IGNORECASE)
        if mm:
            return date(int(mm.group(1)), mo, 1)
    m = re.search(r"(\d{4})-(\d{2})-\d{2}", name)           # 2022-08-09
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    return None


def _col(df: pd.DataFrame, *cands: str) -> Optional[str]:
    for c in cands:
        if c in df.columns:
            return c
    return None


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    xl = pd.ExcelFile(file_path)
    fallback = None
    if period_override:
        d = datetime.strptime(period_override + "-01", "%Y-%m-%d").date()
        fallback = date(d.year, d.month, 1)
    if fallback is None:
        fallback = _month_from_name(Path(file_path).name)

    rows: list[SalesRow] = []
    raw_records: list[dict] = []
    sell_agg: dict[tuple, float] = {}
    stock_agg: dict[tuple, float] = {}

    # --- Продажи ---
    if "Продажи" in xl.sheet_names:
        df = xl.parse("Продажи", header=0, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        c_point = _col(df, "Аптека")
        c_prod = _col(df, "Номенклатура")
        c_qty = _col(df, "Количество", "Количество продаж")
        c_month = _col(df, "Месяц")
        for rec in df.to_dict("records"):
            point = str(rec.get(c_point, "")).strip()
            prod = str(rec.get(c_prod, "")).strip()
            qty = _num(rec.get(c_qty))
            if not point or not prod or qty == 0:
                continue
            per = _parse_month_cell(rec.get(c_month)) if c_month else None
            per = per or fallback
            if per is None:
                raise ValueError("не определил период продаж (нет Месяца и --period)")
            raw_records.append({"_лист": "Продажи", "Месяц": str(rec.get(c_month, "")),
                                "Аптека": point, "Номенклатура": prod, "Кол-во": qty})
            sell_agg[(per, point, prod)] = sell_agg.get((per, point, prod), 0.0) + qty

    # --- Остатки ---
    if "Остатки" in xl.sheet_names:
        df = xl.parse("Остатки", header=0, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        c_point = _col(df, "Аптека")
        c_prod = _col(df, "Номенклатура")
        c_qty = _col(df, "Количество", "Остаток")
        # дата снимка = конец месяца отчёта (из продаж/имени/override)
        smonth = next((p for (p, _, _) in sell_agg), None) or fallback
        for rec in df.to_dict("records"):
            point = str(rec.get(c_point, "")).strip()
            prod = str(rec.get(c_prod, "")).strip()
            qty = _num(rec.get(c_qty))
            if not point or not prod or qty == 0:
                continue
            raw_records.append({"_лист": "Остатки", "Аптека": point,
                                "Номенклатура": prod, "Кол-во": qty})
            stock_agg[(point, prod)] = stock_agg.get((point, prod), 0.0) + qty

    for (per, point, prod), qty in sell_agg.items():
        rows.append(SalesRow(source="sellout", client_name=CLIENT, sku_code=prod,
                             sku_name=prod, tt_code=point, tt_name=point, qty=qty, period=per))

    if stock_agg:
        smonth = next((p for (p, _, _) in sell_agg), None) or fallback
        if smonth is None:
            raise ValueError("не определил месяц для остатков (нет продаж/имени/--period)")
        snap = _eom(smonth)
        for (point, prod), qty in stock_agg.items():
            rows.append(SalesRow(source="stock", client_name=CLIENT, sku_code=prod,
                                 sku_name=prod, tt_code=point, tt_name=point,
                                 qty=qty, snapshot_date=snap))

    return rows, raw_records
