"""Запись в БД: staging (сырьё), core (факты), регистр загрузки."""
import json
from datetime import date
from typing import Optional
from sqlalchemy import text
from sqlalchemy.engine import Connection


def stage_raw(conn: Connection, client_name: str, source: str, file_name: str,
              period: Optional[date], raw_records: list[dict]) -> None:
    if not raw_records:
        return
    conn.execute(
        text("""INSERT INTO staging.raw_upload(client_name, source, file_name, period, payload)
                VALUES (:c, :s, :f, :p, CAST(:payload AS JSONB))"""),
        [
            {"c": client_name, "s": source, "f": file_name, "p": period,
             "payload": json.dumps(rec, ensure_ascii=False, default=str)}
            for rec in raw_records
        ],
    )


_FACT_SQL = {
    "sellout": """INSERT INTO core.fact_sellout(client_id, tt_id, sku_id, period, qty, rub_est, source_file)
                  VALUES (:client_id, :tt_id, :sku_id, :period, :qty, :rub, :file)""",
    "sellin":  """INSERT INTO core.fact_sellin(client_id, sku_id, period, qty, rub, source_file)
                  VALUES (:client_id, :sku_id, :period, :qty, :rub, :file)
                  ON CONFLICT (client_id, sku_id, period, source_file) DO NOTHING""",
    "stock":   """INSERT INTO core.fact_stock(client_id, tt_id, sku_id, snapshot_date, qty, rub_est, source_file)
                  VALUES (:client_id, :tt_id, :sku_id, :snapshot_date, :qty, :rub, :file)""",
    "pos_purchase": """INSERT INTO core.fact_pos_purchase(client_id, tt_id, sku_id, period, qty, rub, source_file)
                  VALUES (:client_id, :tt_id, :sku_id, :period, :qty, :rub, :file)""",
}


_DELETE_SQL = {
    "sellout": "DELETE FROM core.fact_sellout WHERE client_id = :c AND source_file = :f",
    "sellin":  "DELETE FROM core.fact_sellin  WHERE client_id = :c AND source_file = :f",
    "stock":   "DELETE FROM core.fact_stock   WHERE client_id = :c AND source_file = :f",
    "pos_purchase": "DELETE FROM core.fact_pos_purchase WHERE client_id = :c AND source_file = :f",
}


def delete_prior(conn: Connection, source: str, client_id: int, file_name: str) -> None:
    """Идемпотентность: убрать прежнюю загрузку того же файла перед повторной вставкой."""
    conn.execute(text(_DELETE_SQL[source]), {"c": client_id, "f": file_name})


def insert_facts(conn: Connection, source: str, fact_rows: list[dict]) -> int:
    if not fact_rows:
        return 0
    conn.execute(text(_FACT_SQL[source]), fact_rows)
    return len(fact_rows)


def write_load_register(conn: Connection, client_id: int, period: Optional[date],
                        source: str, status: str, file_name: str, rows_loaded: int) -> None:
    conn.execute(
        text("""INSERT INTO core.load_register(client_id, period, source, status, file_name, rows_loaded)
                VALUES (:c, :p, :s, :st, :f, :n)"""),
        {"c": client_id, "p": period, "s": source, "st": status, "f": file_name, "n": rows_loaded},
    )
