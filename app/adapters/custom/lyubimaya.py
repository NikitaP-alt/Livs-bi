"""Любимая аптека (Тула): CSV (cp1251, sep=';'), построчные чеки/приходы.
Журнал «Чеки» -> продажи, «Приход» -> закуп. Товар/Кол-во/Дата/Склад(адрес).
Агрегируем СУММОЙ по (месяц, точка, товар)."""
from __future__ import annotations
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Любимая аптека"


def _num(v) -> Optional[float]:
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _month(v) -> Optional[date]:
    m = re.search(r"(\d{2})\.(\d{2})\.(20\d{2})", str(v))
    return date(int(m.group(3)), int(m.group(2)), 1) if m else None


def adapt(file_path, period_override: Optional[str] = None):
    try:
        df = pd.read_csv(file_path, sep=";", encoding="cp1251", dtype=str).fillna("")
    except Exception:
        df = pd.read_csv(file_path, sep=";", encoding="utf-8", dtype=str).fillna("")
    fname = Path(file_path).name.lower()
    src_default = "pos_purchase" if "закуп" in fname else "sellout"

    agg: dict[tuple, float] = {}
    for rec in df.to_dict("records"):
        prod = str(rec.get("Товар", "")).strip()
        low = prod.lower()
        if not prod or ("livs" not in low and "ливс" not in low):
            continue
        qty = _num(rec.get("Кол-во"))
        if not qty:
            continue
        zh = str(rec.get("Журнал", "")).lower()
        src = ("pos_purchase" if ("приход" in zh or "закуп" in zh)
               else "sellout" if "чек" in zh else src_default)
        tt = str(rec.get("Склад", "")).strip()
        mon = _month(rec.get("Дата"))
        if mon is None:
            continue
        agg[(src, mon, tt, prod)] = agg.get((src, mon, tt, prod), 0.0) + qty

    rows = [SalesRow(source=src, client_name=CLIENT, sku_code=prod, sku_name=prod,
                     qty=q, tt_code=(tt or None), tt_name=(tt or None), period=mon)
            for (src, mon, tt, prod), q in agg.items()]
    return rows, []
