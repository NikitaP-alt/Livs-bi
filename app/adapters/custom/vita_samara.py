"""Переходник: Вита (Самара). Два типа файлов:
- продажи_*  -> sellout. Широкая сводная: строки=товары, колонки=аптеки (Регион|код|...).
               Разворачиваем (unpivot) в строки (товар, аптека, кол-во).
- остатки_*  -> stock. На уровне товара (Остаток Склад + Розница), есть цена закупки.
               Точек нет (агрегат дистрибьютора). rub_est = кол-во * цена.

Товар опознаём по коду (Код / ID_MP — он стабилен и есть в обоих файлах). Период из --period.
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "Вита (Самара)"


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


def _month(override: Optional[str]) -> date:
    if not override:
        raise ValueError("для Вита (Самара) нужен --period YYYY-MM")
    d = datetime.strptime(override + "-01", "%Y-%m-%d").date()
    return date(d.year, d.month, 1)


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _header_row(file_path) -> int:
    raw = pd.read_excel(file_path, header=None, dtype=str, nrows=8).fillna("")
    for i in range(len(raw)):
        if "Наименование" in [str(x).strip() for x in raw.iloc[i].tolist()]:
            return i
    raise ValueError("не нашёл шапку (нет 'Наименование')")


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    hidx = _header_row(file_path)
    df = pd.read_excel(file_path, header=hidx, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)
    raw_records = df.to_dict("records")
    month = _month(period_override)

    def code_of(rec):
        return (str(rec.get("Код", "")).strip() or str(rec.get("ID_MP", "")).strip())

    rows: list[SalesRow] = []
    units_col = next((c for c in cols if c.startswith("Продано") and "Упак" in c), None)
    sklad = next((c for c in cols if c.startswith("Остаток") and "Склад" in c), None)
    rozn = next((c for c in cols if c.startswith("Остаток") and "Розниц" in c), None)

    # колонки-аптеки (старый широкий формат товар×аптека); служебные исключаем
    attrs = {"Код", "Наименование", "Производитель", "ID_MP", "Вывод", "Менеджер",
             "Холдинг", "Тотал сток"}
    skip_pref = ("Группа", "Цены", "Приход", "Остаток", "Продано", "в мес", "остаток в руб")
    pharm = [c for c in cols if c not in attrs and not c.startswith(skip_pref)]

    if not units_col and not sklad and pharm:
        # старый широкий формат: строки=товары, колонки=аптеки -> unpivot
        for rec in raw_records:
            name = str(rec.get("Наименование", "")).strip()
            code = code_of(rec)
            if not name or name.startswith("Общий итог"):
                continue
            for p in pharm:
                v = _num(rec.get(p))
                if v <= 0:
                    continue
                city = p.split("|")[0].strip() if "|" in p else None
                rows.append(SalesRow(source="sellout", client_name=CLIENT,
                                     sku_code=code or name, sku_name=name, qty=v,
                                     tt_code=p, tt_name=p, tt_city=city, period=month))
        return rows, raw_records

    # новый узкий "по изготовителю": в ОДНОМ файле И продажи, И остатки (на уровне товара, без точек)
    rub_col = next((c for c in cols if c.startswith("Продано") and ("Сумма" in c or "ЗЦ" in c)), None)
    price_col = next((c for c in cols if c.startswith("Цены")), None)
    for rec in raw_records:
        name = str(rec.get("Наименование", "")).strip()
        code = code_of(rec)
        if not name or name.startswith("Общий итог"):
            continue
        # продажи (sell-out)
        if units_col:
            qs = _num(rec.get(units_col))
            if qs > 0:
                rub = _num(rec.get(rub_col)) if rub_col else 0.0
                rows.append(SalesRow(source="sellout", client_name=CLIENT,
                                     sku_code=code or name, sku_name=name,
                                     qty=qs, rub=(rub or None), period=month))
        # остатки (Склад + Розница)
        qst = (_num(rec.get(sklad)) if sklad else 0.0) + (_num(rec.get(rozn)) if rozn else 0.0)
        if qst > 0:
            price = _num(rec.get(price_col)) if price_col else 0.0
            rows.append(SalesRow(source="stock", client_name=CLIENT,
                                 sku_code=code or name, sku_name=name,
                                 qty=qst, rub=(round(qst * price, 2) if price else None),
                                 snapshot_date=_eom(month)))

    return rows, raw_records
