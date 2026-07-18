"""CLI-оркестратор загрузки.

Примеры:
  python -m app.ingest load --config app/adapters/configs/example_client.yaml \\
                            --file sample_data/sellout_example.csv
  python -m app.ingest queue
  python -m app.ingest confirm-sku --client "Аптека Пример" --code CL-100 \\
                            --article LIVS-VITC --name "ЛИВС Витамин С"
"""
import argparse
import importlib
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy import text

from .config import get_engine
from .adapters.base import load_config, adapt
from .loader import stage_raw, insert_facts, write_load_register, delete_prior
from .mapping import (
    get_or_create_client, get_or_create_tt, resolve_sku, enqueue_sku, confirm_sku,
    auto_create_sku,
)


def _client_id(conn, name: str) -> int:
    row = conn.execute(
        text("SELECT client_id FROM core.dim_client WHERE name = :n"), {"n": name}
    ).fetchone()
    if not row:
        raise SystemExit(f"Клиент не найден: {name!r}")
    return row[0]


def _build_fact(source: str, client_id: int, sku_id: int, tt_id, r, file_name: str) -> dict:
    fr = {"client_id": client_id, "sku_id": sku_id, "qty": r.qty, "file": file_name}
    if source == "sellin":
        fr.update({"period": r.period, "rub": r.rub})
    elif source == "stock":
        fr.update({"tt_id": tt_id, "snapshot_date": r.snapshot_date, "rub": r.rub})
    else:  # sellout | pos_purchase
        fr.update({"tt_id": tt_id, "period": r.period, "rub": r.rub})
    return fr


def _load_rows(args, client_name: str, rows: list, raw: list[dict], file_name: str) -> dict:
    by_source: dict[str, list] = defaultdict(list)
    for r in rows:
        by_source[r.source].append(r)

    summary: dict[str, tuple] = {}
    engine = get_engine()
    with engine.begin() as conn:
        client_id = get_or_create_client(conn, client_name)
        any_period = next((r.period for r in rows if r.period), None)
        stage_tag = "mixed" if len(by_source) > 1 else next(iter(by_source), "n/a")
        stage_raw(conn, client_name, stage_tag, file_name, any_period, raw)

        for source, srows in by_source.items():
            fact_rows, queued = [], 0
            for r in srows:
                sku_id = resolve_sku(conn, client_id, r.sku_code)
                if sku_id is None:
                    if args.auto_sku:
                        sku_id = auto_create_sku(conn, client_id, r.sku_code, r.sku_name)
                    else:
                        enqueue_sku(conn, client_id, r.sku_code, r.sku_name)
                        queued += 1
                        continue
                tt_id = None
                if source in ("sellout", "stock", "pos_purchase"):
                    tt_id = get_or_create_tt(conn, client_id, r.tt_code, r.tt_name,
                                             r.tt_chain, r.tt_city, r.tt_inn)
                fact_rows.append(_build_fact(source, client_id, sku_id, tt_id, r, file_name))

            delete_prior(conn, source, client_id, file_name)
            loaded = insert_facts(conn, source, fact_rows)
            reg_period = next((r.period for r in srows if r.period), None)
            if reg_period is None:
                sd = next((r.snapshot_date for r in srows if r.snapshot_date), None)
                if sd:
                    reg_period = date(sd.year, sd.month, 1)
            write_load_register(conn, client_id, reg_period, source, "loaded", file_name, loaded)
            summary[source] = (loaded, queued)
    return summary


def cmd_load(args) -> None:
    file_name = Path(args.file).name
    if args.adapter:
        mod = importlib.import_module(f"app.adapters.custom.{args.adapter}")
        client_name = mod.CLIENT
        rows, raw = mod.adapt(args.file, args.period)
    elif args.config:
        cfg = load_config(args.config)
        client_name = cfg["client"]
        rows, raw = adapt(cfg, args.file, args.period)
    else:
        raise SystemExit("укажи --config (YAML) или --adapter (python-модуль)")

    summary = _load_rows(args, client_name, rows, raw, file_name)
    print(f"Клиент: {client_name} | файл: {file_name} | строк распознано: {len(rows)}")
    total_q = 0
    for source, (loaded, queued) in summary.items():
        print(f"  [{source}] в core: {loaded}; в очередь SKU: {queued}")
        total_q += queued
    if total_q:
        print("  -> сопоставь SKU: python -m app.ingest queue / confirm-sku, затем повтори load")


def cmd_queue(args) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(text(
            """SELECT q.kind, c.name, q.raw_code, q.raw_name
               FROM core.mapping_queue q
               LEFT JOIN core.dim_client c ON c.client_id = q.client_id
               WHERE q.status = 'pending'
               ORDER BY c.name, q.kind, q.raw_code"""
        )).fetchall()
    if not rows:
        print("Очередь пуста.")
        return
    print(f"Ожидают сопоставления ({len(rows)}):")
    for kind, client, code, name in rows:
        print(f"  [{kind}] {client}: {code}  —  {name or ''}")


def cmd_confirm_sku(args) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        cid = _client_id(conn, args.client)
        sku_id = confirm_sku(conn, cid, args.code, args.article, args.name, args.barcode)
    print(f"OK: {args.client} / {args.code} -> sku_id={sku_id} ({args.article})")


def main() -> None:
    p = argparse.ArgumentParser(prog="app.ingest")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("load", help="загрузить файл через переходник")
    pl.add_argument("--config", help="путь к YAML-переходнику (для простых клиентов)")
    pl.add_argument("--adapter", help="имя python-переходника из app/adapters/custom (для сложных)")
    pl.add_argument("--file", required=True)
    pl.add_argument("--period", help="YYYY-MM (или YYYY-MM-DD для stock), если период не в файле")
    pl.add_argument("--auto-sku", action="store_true",
                    help="провизорно создавать SKU из наименования (быстрый старт на реальных данных)")
    pl.set_defaults(func=cmd_load)

    pq = sub.add_parser("queue", help="показать очередь сопоставлений")
    pq.set_defaults(func=cmd_queue)

    pc = sub.add_parser("confirm-sku", help="подтвердить сопоставление кода клиента -> артикул ЛИВС")
    pc.add_argument("--client", required=True)
    pc.add_argument("--code", required=True)
    pc.add_argument("--article", required=True)
    pc.add_argument("--name", required=True)
    pc.add_argument("--barcode")
    pc.set_defaults(func=cmd_confirm_sku)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
