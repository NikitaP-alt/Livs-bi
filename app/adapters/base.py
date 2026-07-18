"""Движок переходника: по YAML-конфигу превращает файл клиента в канонические строки.

Один конфиг = один клиент + один тип отчёта (sellout/stock/sellin).
Под нового клиента правится только YAML — код переходника общий.
"""
from __future__ import annotations
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from ..canonical import SalesRow


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_number(val, decimal: str = ",", thousands: str = " ") -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace("\xa0", "")
    if s == "":
        return None
    if thousands:
        s = s.replace(thousands, "")
    s = s.replace(" ", "")
    if decimal and decimal != ".":
        s = s.replace(decimal, ".")
    try:
        return float(s)
    except ValueError:
        return None


def _to_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _parse_date(value: str, fmt: str) -> date:
    return datetime.strptime(str(value).strip(), fmt).date()


def _signatures(cfg: dict) -> list:
    """Имена-кандидаты колонок sku_code и qty (для авто-поиска строки заголовка)."""
    cols = cfg.get("columns", {})
    sig = []
    for f in ("sku_code", "qty"):
        spec = cols.get(f)
        if spec:
            sig += spec if isinstance(spec, list) else [spec]
    return sig


def _detect_header(file_path, sheet, sigs: list, look: int = 15) -> int:
    raw = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str, nrows=look).fillna("")
    for i in range(len(raw)):
        rowvals = [str(x).strip() for x in raw.iloc[i].tolist()]
        if any(s in rowvals for s in sigs):
            return i
    return 0


def _read_table(cfg: dict, file_path: str | Path) -> pd.DataFrame:
    file_type = cfg.get("file_type", "excel")
    header = cfg.get("header_row", 0)
    if file_type != "csv" and cfg.get("header_detect"):
        header = _detect_header(file_path, cfg.get("sheet", 0), _signatures(cfg))
    if file_type == "csv":
        df = pd.read_csv(
            file_path,
            sep=cfg.get("sep", ","),
            dtype=str,
            keep_default_na=False,
            encoding=cfg.get("encoding", "utf-8"),
            header=header,
        )
    else:
        df = pd.read_excel(
            file_path,
            sheet_name=cfg.get("sheet", 0),
            dtype=str,
            header=header,
        ).fillna("")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def adapt(cfg: dict, file_path: str | Path, period_override: Optional[str] = None):
    """Возвращает (canonical_rows: list[SalesRow], raw_records: list[dict])."""
    source = cfg["source"]
    cols = cfg["columns"]
    dec = cfg.get("decimal", ",")
    thou = cfg.get("thousands", " ")
    df = _read_table(cfg, file_path)
    raw_records = df.to_dict("records")

    # Поддержка алиасов: значение колонки в конфиге может быть строкой ИЛИ списком
    # кандидатов (для дрейфа формата) — берём первый, который реально есть в файле.
    present = set(df.columns)

    def pick(field: str):
        spec = cols.get(field)
        if spec is None:
            return None
        for c in (spec if isinstance(spec, list) else [spec]):
            if c in present:
                return c
        return None

    R = {f: pick(f) for f in ("sku_code", "sku_name", "qty", "rub",
                              "tt_code", "tt_name", "tt_inn", "tt_city", "tt_chain")}
    compose = cfg.get("tt_compose")   # список колонок -> склеить в ключ точки
    if not R["sku_code"] or not R["qty"]:
        raise ValueError(f"не нашёл колонки sku_code/qty. Колонки файла: {sorted(present)}")

    pcfg = cfg.get("period", {})
    pmode = pcfg.get("mode", "from_arg")

    rows: list[SalesRow] = []
    for rec in raw_records:
        sku_code = str(rec.get(R["sku_code"], "")).strip()
        qty = parse_number(rec.get(R["qty"]), dec, thou)
        if sku_code == "" or qty is None:
            continue  # пустая строка
        if any(t in sku_code.lower() for t in ("итог", "всего", "total")):
            continue  # строка-итог в подвале файла

        def g(key):
            c = R[key]
            v = str(rec.get(c, "")).strip() if c else ""
            return v or None

        if compose:
            parts = [str(rec.get(c, "")).strip() for c in compose if c in present]
            tt_code = "|".join(p for p in parts if p) or None
        else:
            tt_code = g("tt_code")

        row = SalesRow(
            source=source,
            client_name=cfg["client"],
            sku_code=sku_code,
            qty=qty,
            sku_name=g("sku_name"),
            rub=(parse_number(rec.get(R["rub"]), dec, thou) if R["rub"] else None),
            tt_code=tt_code,
            tt_name=g("tt_name"),
            tt_inn=g("tt_inn"),
            tt_city=g("tt_city"),
            tt_chain=g("tt_chain"),
        )

        if source == "stock":
            if pmode == "from_column":
                row.snapshot_date = _parse_date(rec[pcfg["column"]], pcfg.get("format", "%Y-%m-%d"))
            else:
                if not period_override:
                    raise ValueError("Для stock нужен --period в формате YYYY-MM-DD")
                row.snapshot_date = _parse_date(period_override, "%Y-%m-%d")
        else:  # sellin / sellout — месяц
            if pmode == "from_column":
                d = _parse_date(rec[pcfg["column"]], pcfg.get("format", "%Y-%m"))
            else:
                if not period_override:
                    raise ValueError("Нужен --period в формате YYYY-MM")
                d = _parse_date(period_override + "-01", "%Y-%m-%d")
            row.period = _to_month(d)

        rows.append(row)

    return rows, raw_records
