"""Переходник: НеоФарм (1С-выгрузки). Три типа файлов (по отдельности):
- закупки_*  -> pos_purchase (есть «Код номенклатуры», «Сумма закупки»)
- остатки_*  -> stock        (есть «Срок годности»)
- продажи_*  -> sellout      (шапка не на 1-й строке: «Продажи по номенклатуре» + подытоги)

Тип файла определяется автоматически по колонкам. Период — из --period (он в имени файла).
Строки по партиям/приходам -> агрегируем СУММОЙ по (номенклатура, адрес, юрлицо).
Товар опознаём по наименованию (в продажах/остатках кода нет).
"""
from __future__ import annotations
import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from ...canonical import SalesRow

CLIENT = "НеоФарм"


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
        raise ValueError("для НеоФарм нужен --period YYYY-MM (он в имени файла)")
    d = datetime.strptime(override + "-01", "%Y-%m-%d").date()
    return date(d.year, d.month, 1)


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def adapt(file_path: str | Path, period_override: Optional[str] = None):
    raw = pd.read_excel(file_path, header=None, dtype=str).fillna("")
    n = len(raw)

    # 1) найти строку-шапку (содержит "Номенклатура")
    header_idx = None
    for i in range(min(n, 20)):
        if "Номенклатура" in [str(x).strip() for x in raw.iloc[i].tolist()]:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError("не нашёл шапку (нет колонки 'Номенклатура')")

    namerow = [str(x).strip() for x in raw.iloc[header_idx].tolist()]
    above = ([str(x).strip() for x in raw.iloc[header_idx - 1].tolist()]
             if header_idx > 0 else [""] * len(namerow))
    names = [namerow[i] or (above[i] if i < len(above) else "") for i in range(len(namerow))]

    def idx(*cands):
        for i, nm in enumerate(names):
            if nm in cands:
                return i
        return None

    i_nom = idx("Номенклатура")
    i_qty = idx("Количество")
    i_pod = idx("Подразделение")
    i_sum = idx("Исходная сумма закупки", "Сумма закупки")
    i_code = idx("Код номенклатуры")
    i_org = idx("Организация")
    i_inn = idx("ИНН организации")
    i_contr = idx("Партия.Контрагент")
    i_srok = idx("Партия.Серия.Срок годности", "Срок годности")

    # тип факта: сначала по имени файла (надёжно к смене формата), иначе по колонкам
    nl = str(file_path).lower()
    if "закуп" in nl:
        source = "pos_purchase"
    elif "остат" in nl:
        source = "stock"
    elif "продаж" in nl or "реализ" in nl:
        source = "sellout"
    elif i_code is not None:
        source = "pos_purchase"
    elif i_srok is not None:
        source = "stock"
    else:
        source = "sellout"

    month = _month(period_override)

    # staging: сырые строки данных как dict по именам колонок
    uniq, seen = [], {}
    for c in (names[i] or f"col{i}" for i in range(len(names))):
        seen[c] = seen.get(c, -1) + 1
        uniq.append(c if seen[c] == 0 else f"{c}_{seen[c]}")
    data = raw.iloc[header_idx + 1:].values.tolist()
    raw_records = [dict(zip(uniq, [str(x) for x in row])) for row in data]

    agg: dict[tuple, list] = {}
    for row in data:
        nom = str(row[i_nom]).strip() if i_nom is not None else ""
        pod = str(row[i_pod]).strip() if i_pod is not None else ""
        if not nom or not pod:
            continue  # подытоги/группировки/пустые
        qty = _num(row[i_qty]) if i_qty is not None else 0.0
        if qty == 0:
            continue
        rub = _num(row[i_sum]) if i_sum is not None else 0.0
        chain = ""
        if i_org is not None and str(row[i_org]).strip():
            chain = str(row[i_org]).strip()
        elif i_contr is not None:
            chain = str(row[i_contr]).strip()
        inn = str(row[i_inn]).strip() if i_inn is not None else ""
        key = (nom, pod, chain, inn)
        a = agg.setdefault(key, [0.0, 0.0])
        a[0] += qty
        a[1] += rub

    rows: list[SalesRow] = []
    for (nom, pod, chain, inn), (qty, rub) in agg.items():
        common = dict(
            client_name=CLIENT,
            sku_code=nom, sku_name=nom,
            tt_code=pod, tt_name=pod,
            tt_chain=chain or None, tt_inn=inn or None,
        )
        if source == "stock":
            rows.append(SalesRow(source="stock", qty=qty, rub=(rub or None),
                                 snapshot_date=_eom(month), **common))
        else:  # sellout | pos_purchase
            rows.append(SalesRow(source=source, qty=qty, rub=(rub or None),
                                 period=month, **common))

    return rows, raw_records
