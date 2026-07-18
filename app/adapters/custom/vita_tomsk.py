"""Переходник: дистрибьютор Вита-Фарм (отчёт «Вита Томск»).

Особенности этого отчёта:
- один файл = 3 факта: закуп точки (вторичка), продажи (sell-out), остаток (stock);
- строки по партиям прихода (накладная/срок годности) -> агрегируем СУММОЙ
  по (месяц, ИНН юрлица, юрлицо, город, адрес, товар);
- товар опознаём по наименованию (кода/штрихкода нет);
- точка = адрес; юрлицо/сеть, город, ИНН — атрибуты точки.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Вита-Фарм"

COL = {
    "period": "Период отчета",
    "sku": "Товар",
    "buy_qty": "Закуп шт.",
    "buy_rub": "Закуп сумма с НДС",
    "sell_qty": "Продажи шт.",
    "stock_qty": "Остаток на конец периода шт.",
    "inn": "ИНН Юр.лица",
    "entity": "Юр.лицо",
    "city": "Населенный пункт",
    "address": "Адрес аптеки",
}


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


def _month(v, override: Optional[str]) -> date:
    s = str(v).strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt).date()
            return date(d.year, d.month, 1)
        except ValueError:
            pass
    if override:
        d = datetime.strptime(override + "-01", "%Y-%m-%d").date()
        return date(d.year, d.month, 1)
    raise ValueError(f"не распознан период: {v!r}")


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    df = pd.read_excel(file_path, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    raw_records = df.to_dict("records")

    df["_m"] = df[COL["period"]].map(lambda v: _month(v, period_override))
    for k in ("buy_qty", "buy_rub", "sell_qty", "stock_qty"):
        df[k] = df[COL[k]].map(_num)

    keys = ["_m", COL["inn"], COL["entity"], COL["city"], COL["address"], COL["sku"]]
    g = (df.groupby(keys, dropna=False)
           .agg(buy_qty=("buy_qty", "sum"), buy_rub=("buy_rub", "sum"),
                sell_qty=("sell_qty", "sum"), stock_qty=("stock_qty", "sum"))
           .reset_index())

    rows: list[SalesRow] = []
    for r in g.to_dict("records"):
        month = r["_m"]
        inn = str(r[COL["inn"]]).strip()
        address = str(r[COL["address"]]).strip()
        sku = str(r[COL["sku"]]).strip()
        if not sku or not address:
            continue
        common = dict(
            client_name=CLIENT,
            sku_code=sku, sku_name=sku,
            tt_code=f"{inn}|{address}", tt_name=address,
            tt_chain=str(r[COL["entity"]]).strip(),
            tt_city=str(r[COL["city"]]).strip(),
            tt_inn=inn,
        )
        if r["sell_qty"]:
            rows.append(SalesRow(source="sellout", qty=r["sell_qty"], period=month, **common))
        if r["buy_qty"]:
            rows.append(SalesRow(source="pos_purchase", qty=r["buy_qty"],
                                 rub=(r["buy_rub"] or None), period=month, **common))
        if r["stock_qty"]:
            rows.append(SalesRow(source="stock", qty=r["stock_qty"], snapshot_date=_eom(month), **common))

    return rows, raw_records
