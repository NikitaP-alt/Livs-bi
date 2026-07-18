"""Авто-переходник: разбирает произвольный Excel БЕЗ ручного конфига.

Логика:
1. Для каждого листа ищем строку-шапку (макс. совпадений со словарём синонимов).
2. По синонимам определяем колонки: товар, код товара, точка, ИНН, город, период
   и МЕТРИКИ-количества (продажи/остаток/закуп) — по одной колонке на тип факта.
3. Денежные колонки (руб/сумма/цена/НДС/выручка) в количество НЕ берём.
4. Грузим только бренд ЛИВС; строки-итоги пропускаем.
Период — из пути (period_override) или из колонки «Период/Месяц».
Возвращает (rows, raw_records). Если ничего не распознал — пустой результат.
"""
from __future__ import annotations
import re
import os
import tempfile
import zipfile
from datetime import date, datetime
import calendar
from pathlib import Path
from typing import Optional

import pandas as pd

from ..canonical import SalesRow


def _fix_xlsx(path: str) -> str:
    """Некоторые экспортёры кладут 'xl/SharedStrings.xml' (др. регистр) — openpyxl падает.
    Если так — пересобираем архив с правильным именем и возвращаем путь к временному файлу."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
    except zipfile.BadZipFile:
        return path
    target = "xl/sharedStrings.xml"
    variant = next((n for n in names if n.lower() == target.lower() and n != target), None)
    if not variant:
        return path
    fd, tmp = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for it in zin.infolist():
            zout.writestr(target if it.filename == variant else it.filename, zin.read(it.filename))
    return tmp

MONEY = ("руб", "сумма", "сумм", "цена", "ндс", "стоим", "выручк", "сип", "%", "доля", "оплач", "бонус")
RU = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6, "июль": 7,
      "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12}

SYN = {
    "product":  ("наименование", "товар", "номенклатур", "препарат", "продукт", "аналог", "ассортимент"),
    "prodcode": ("артикул", "код товар", "код номенклат", "sku id", "код гес", "id_mp", "коданалог", "код ап"),
    "pointcode": ("код аптек", "id аптек", "номер аптек", "код тт", "код тт"),
    "pointname": ("аптека", "клиент", "краткое наименование", "адрес аптек", "точка", "склад", "подразделение", "организация", "отдел"),
    "inn":      ("инн",),
    "city":     ("город", "населен"),
    "chain":    ("бренд", "юр.лицо", "юрлицо", "юр лицо", "филиал", "сеть", "представительств"),
    "address":  ("адрес", "улица", "сводный адрес"),
    "period":   ("период", "месяц", "год - месяц", "дата отч"),
}


def _num(v) -> Optional[float]:
    s = str(v).strip().replace("\xa0", "").replace(" ", "")
    if s == "":
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _eom(m: date) -> date:
    return date(m.year, m.month, calendar.monthrange(m.year, m.month)[1])


def _is_livs(name: str) -> bool:
    n = name.lower()
    return "livs" in n or "ливс" in n or "lvs" in n


def _is_total(name: str) -> bool:
    n = name.lower()
    return any(t in n for t in ("итог", "всего", "total"))


def _find(cols, keys, exclude=()):
    for c in cols:
        cl = str(c).lower()
        if any(k in cl for k in keys) and not any(e in cl for e in exclude):
            return c
    return None


def _metrics(cols):
    """{'sellout'|'stock'|'pos_purchase': имя_колонки} — по одной (первой) на тип, без денег."""
    out = {}
    for c in cols:
        cl = str(c).lower()
        if any(mm in cl for mm in MONEY):
            continue
        if "сумкол" in cl:  # Гармония: СумКол=продажи, СумКолОстКП=остаток
            out.setdefault("stock" if ("остк" in cl or "ост.к" in cl) else "sellout", c)
        elif "остат" in cl or "сток" in cl:
            out.setdefault("stock", c)
        elif "закуп" in cl or "приход" in cl or "поставк" in cl:
            out.setdefault("pos_purchase", c)
        elif "продаж" in cl or "продано" in cl or "реализ" in cl or "sell" in cl:
            out.setdefault("sellout", c)
    # «Количество/Кол-во» без явного типа — трактуем по подсказке имени файла (в adapt)
    return out


def _qty_generic(cols):
    for c in cols:
        cl = str(c).lower()
        if any(mm in cl for mm in MONEY):
            continue
        if (cl.strip() in ("количество", "кол-во", "шт", "уп", "штук", "количество, уп")
                or "кол-во" in cl or "количество" in cl):
            return c
    return None


def _header_row(raw: pd.DataFrame) -> Optional[int]:
    allkeys = sum(SYN.values(), ()) + ("количество", "кол-во", "продаж", "остат", "закуп")
    best_i, best_n = None, 1
    for i in range(min(len(raw), 20)):
        vals = [str(x).lower() for x in raw.iloc[i].tolist() if str(x).strip()]
        n = sum(1 for v in vals if any(k in v for k in allkeys))
        if n > best_n:
            best_i, best_n = i, n
    return best_i


def _parse_period_cell(val) -> Optional[date]:
    s = str(val).strip()
    m = re.match(r"(20\d{2})[-.](\d{2})", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    m = re.search(r"(\d{2})\.(20\d{2})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    for w, mo in RU.items():
        if w in s.lower():
            y = re.search(r"20\d{2}", s)
            if y:
                return date(int(y.group(0)), mo, 1)
    return None


def adapt(file_path, period_override: Optional[str], client_name: str):
    fhint = Path(file_path).name.lower()
    fp = _fix_xlsx(str(file_path))
    base_month = None
    if period_override:
        d = datetime.strptime(period_override + "-01", "%Y-%m-%d").date()
        base_month = date(d.year, d.month, 1)

    xl = pd.ExcelFile(fp)
    rows: list[SalesRow] = []
    raw_records: list[dict] = []

    for sheet in xl.sheet_names:
        try:
            head = pd.read_excel(fp, sheet_name=sheet, header=None, dtype=str, nrows=20).fillna("")
        except Exception:
            continue
        hi = _header_row(head)
        if hi is None:
            continue
        df = pd.read_excel(fp, sheet_name=sheet, header=hi, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        cols = list(df.columns)

        c_prod = _find(cols, SYN["product"],
                       exclude=("код", "групп", "аптек", "представ", "юр", "отдел", "склад", "регион"))
        metrics = _metrics(cols)
        if not metrics:
            qg = _qty_generic(cols)
            if qg:
                src = ("stock" if "остат" in fhint else
                       "pos_purchase" if ("закуп" in fhint or "приход" in fhint) else "sellout")
                metrics = {src: qg}
        if not c_prod or not metrics:
            continue

        c_pcode = _find(cols, SYN["prodcode"])
        c_ptcode = _find(cols, SYN["pointcode"])
        c_ptname = _find(cols, SYN["pointname"], exclude=("инн", "код"))
        c_inn = _find(cols, SYN["inn"])
        c_city = _find(cols, SYN["city"])
        c_chain = _find(cols, SYN["chain"])
        c_addr = _find(cols, SYN["address"], exclude=("аптек",)) or _find(cols, ("адрес",))
        c_per = _find(cols, SYN["period"])

        for rec in df.to_dict("records"):
            name = str(rec.get(c_prod, "")).strip()
            if not name or _is_total(name) or not _is_livs(name):
                continue
            # период
            per = base_month
            if c_per and not per:
                per = _parse_period_cell(rec.get(c_per))
            if c_per and per is None:
                per = _parse_period_cell(rec.get(c_per))
            inn = str(rec.get(c_inn, "")).strip() if c_inn else None
            city = str(rec.get(c_city, "")).strip() if c_city else None
            chain = str(rec.get(c_chain, "")).strip() if c_chain else None
            ptname = str(rec.get(c_ptname, "")).strip() if c_ptname else None
            ptcode = str(rec.get(c_ptcode, "")).strip() if c_ptcode else None
            addr = str(rec.get(c_addr, "")).strip() if c_addr else None
            if ptcode:
                tt_code = ptcode
            else:
                parts = [p for p in (inn, city, addr or ptname) if p]
                tt_code = "|".join(parts) if parts else None
            scode = str(rec.get(c_pcode, "")).strip() if c_pcode else ""
            sku_code = scode or name

            for source, qcol in metrics.items():
                qty = _num(rec.get(qcol))
                if not qty:
                    continue
                r = SalesRow(source=source, client_name=client_name, sku_code=sku_code,
                             sku_name=name, qty=qty, tt_code=tt_code, tt_name=ptname or addr,
                             tt_inn=inn or None, tt_city=city or None, tt_chain=chain or None)
                if source == "stock":
                    if not per:
                        continue
                    r.snapshot_date = _eom(per)
                else:
                    if not per:
                        continue
                    r.period = per
                rows.append(r)
        raw_records.append({"_лист": sheet, "_строк": len(df), "_метрики": ",".join(metrics)})

    return rows, raw_records
