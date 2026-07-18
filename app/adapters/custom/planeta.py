"""Переходник: ПланетаЗдоровья. Два нужных типа файлов:
- «Продажи и остатки» -> sellout (Продажи кол-во) + stock (Остатки кол-во), по точкам.
- «Закуп на аптеки»   -> pos_purchase (Кол-во), по точкам.
(«Срок годности» и «Тихоликвиды» не грузим — это не факты продаж.)

Шапка на 4-й строке; период берём из текста файла («За период: с DD.MM.YYYY»).
Товар = Код ГЕС, точка = Код аптеки; сеть/ИНН/регион — атрибуты точки. Рублей в отчёте нет.
"""
from __future__ import annotations
import calendar
import re
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "ПланетаЗдоровья"
_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


def _num(v) -> float:
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s == "":
        return 0.0
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    raw = pd.read_excel(file_path, header=None, dtype=str).fillna("")

    # период: первая дата вида DD.MM.YYYY в первых строках
    month = None
    for i in range(min(4, len(raw))):
        joined = " ".join(str(x) for x in raw.iloc[i].tolist())
        m = _DATE_RE.search(joined)
        if m:
            month = date(int(m.group(3)), int(m.group(2)), 1)
            break
    if month is None and period_override:
        month = date(int(period_override[:4]), int(period_override[5:7]), 1)
    if month is None:
        raise ValueError("не нашёл период в файле и нет --period")

    # шапка: строка с "Код ГЕС"
    header_idx = None
    for i in range(min(8, len(raw))):
        if "Код ГЕС" in [str(x).strip() for x in raw.iloc[i].tolist()]:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("не нашёл шапку (нет 'Код ГЕС')")

    names = [str(x).strip() for x in raw.iloc[header_idx].tolist()]

    def col(*cands):
        for i, nm in enumerate(names):
            if nm in cands:
                return i
        return None

    i_code = col("Код ГЕС")
    i_name = col("Наименование товара", "Товар")
    i_region = col("Регион")
    i_addr = col("Аптека")
    i_ttcode = col("Код аптеки")
    i_entity = col("Юр.лицо")
    i_inn = col("ИНН")
    i_sell = col("Продажи (кол-во)")
    i_stock = col("Остатки (кол-во)")
    i_buy = col("Кол-во")  # в "Закуп на аптеки"

    is_prodstock = i_sell is not None
    data = raw.iloc[header_idx + 1:].values.tolist()

    uniq, seen = [], {}
    for c in (names[i] or f"col{i}" for i in range(len(names))):
        seen[c] = seen.get(c, -1) + 1
        uniq.append(c if seen[c] == 0 else f"{c}_{seen[c]}")
    raw_records = [dict(zip(uniq, [str(x) for x in row])) for row in data]

    # агрегируем по (товар, точка)
    agg: dict[tuple, dict] = {}
    for row in data:
        code = str(row[i_code]).strip() if i_code is not None else ""
        ttcode = str(row[i_ttcode]).strip() if i_ttcode is not None else ""
        if not code or not ttcode:
            continue
        key = (code, ttcode)
        a = agg.setdefault(key, {
            "name": str(row[i_name]).strip() if i_name is not None else code,
            "addr": str(row[i_addr]).strip() if i_addr is not None else "",
            "chain": str(row[i_entity]).strip() if i_entity is not None else "",
            "inn": str(row[i_inn]).strip() if i_inn is not None else "",
            "city": str(row[i_region]).strip() if i_region is not None else "",
            "sell": 0.0, "stock": 0.0, "buy": 0.0,
        })
        if i_sell is not None:
            a["sell"] += _num(row[i_sell])
        if i_stock is not None:
            a["stock"] += _num(row[i_stock])
        if i_buy is not None:
            a["buy"] += _num(row[i_buy])

    rows: list[SalesRow] = []
    for (code, ttcode), a in agg.items():
        common = dict(
            client_name=CLIENT, sku_code=code, sku_name=a["name"],
            tt_code=ttcode, tt_name=a["addr"] or ttcode,
            tt_chain=a["chain"] or None, tt_inn=a["inn"] or None, tt_city=a["city"] or None,
        )
        if is_prodstock:
            if a["sell"] > 0:
                rows.append(SalesRow(source="sellout", qty=a["sell"], period=month, **common))
            if a["stock"] > 0:
                rows.append(SalesRow(source="stock", qty=a["stock"], snapshot_date=_eom(month), **common))
        else:
            if a["buy"] > 0:
                rows.append(SalesRow(source="pos_purchase", qty=a["buy"], period=month, **common))

    return rows, raw_records
