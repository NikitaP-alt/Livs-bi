"""Резолвинг справочников.

Правило:
- Торговая точка (ТТ) АВТО-создаётся под клиентом при первой встрече кода
  (код точки принадлежит клиенту — двусмысленности нет).
- Товар (SKU) требует подтверждённого сопоставления `код клиента -> наш артикул`.
  Если сопоставления нет — код уходит в очередь (mapping_queue), строка в core не пишется.
"""
from typing import Optional
from sqlalchemy import text
from sqlalchemy.engine import Connection


def get_or_create_client(conn: Connection, name: str) -> int:
    row = conn.execute(
        text("SELECT client_id FROM core.dim_client WHERE name = :n"), {"n": name}
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("INSERT INTO core.dim_client(name) VALUES (:n) RETURNING client_id"),
        {"n": name},
    ).scalar_one()


def get_or_create_tt(conn: Connection, client_id: int, tt_code: Optional[str],
                     name: Optional[str] = None, chain: Optional[str] = None,
                     city: Optional[str] = None, inn: Optional[str] = None) -> Optional[int]:
    if not tt_code:
        return None
    row = conn.execute(
        text("""SELECT tt_id FROM core.dim_tt
                WHERE client_id = :c AND client_tt_code = :code"""),
        {"c": client_id, "code": tt_code},
    ).fetchone()
    if row:
        return row[0]
    return conn.execute(
        text("""INSERT INTO core.dim_tt(client_id, client_tt_code, name, chain_name, city, inn)
                VALUES (:c, :code, :name, :chain, :city, :inn) RETURNING tt_id"""),
        {"c": client_id, "code": tt_code, "name": name,
         "chain": chain, "city": city, "inn": inn},
    ).scalar_one()


def auto_create_sku(conn: Connection, client_id: int, code: str, name: Optional[str]) -> int:
    """Провизорно создать SKU из наименования (без канонического артикула) и привязать код клиента.
    Используется флагом --auto-sku для быстрой работы на реальных данных до появления мастер-списка артикулов."""
    sku_id = conn.execute(
        text("INSERT INTO core.dim_sku(livs_article, name) VALUES (NULL, :n) RETURNING sku_id"),
        {"n": name or code},
    ).scalar_one()
    conn.execute(
        text("""INSERT INTO core.map_client_sku(client_id, client_sku_code, sku_id)
                VALUES (:c, :code, :s)
                ON CONFLICT (client_id, client_sku_code) DO NOTHING"""),
        {"c": client_id, "code": code, "s": sku_id},
    )
    return sku_id


def resolve_sku(conn: Connection, client_id: int, sku_code: str) -> Optional[int]:
    row = conn.execute(
        text("""SELECT sku_id FROM core.map_client_sku
                WHERE client_id = :c AND client_sku_code = :code"""),
        {"c": client_id, "code": sku_code},
    ).fetchone()
    return row[0] if row else None


def enqueue_sku(conn: Connection, client_id: int, raw_code: str, raw_name: Optional[str]) -> None:
    conn.execute(
        text("""INSERT INTO core.mapping_queue(kind, client_id, raw_code, raw_name)
                VALUES ('sku', :c, :code, :name)
                ON CONFLICT (kind, client_id, raw_code) DO NOTHING"""),
        {"c": client_id, "code": raw_code, "name": raw_name},
    )


def confirm_sku(conn: Connection, client_id: int, raw_code: str,
                livs_article: str, name: str, barcode: Optional[str] = None) -> int:
    """Подтвердить сопоставление: создать (при необходимости) наш SKU и привязать код клиента."""
    sku = conn.execute(
        text("SELECT sku_id FROM core.dim_sku WHERE livs_article = :a"),
        {"a": livs_article},
    ).fetchone()
    if sku:
        sku_id = sku[0]
    else:
        sku_id = conn.execute(
            text("""INSERT INTO core.dim_sku(livs_article, name, barcode)
                    VALUES (:a, :n, :b) RETURNING sku_id"""),
            {"a": livs_article, "n": name, "b": barcode},
        ).scalar_one()
    conn.execute(
        text("""INSERT INTO core.map_client_sku(client_id, client_sku_code, sku_id)
                VALUES (:c, :code, :s)
                ON CONFLICT (client_id, client_sku_code) DO UPDATE SET sku_id = EXCLUDED.sku_id"""),
        {"c": client_id, "code": raw_code, "s": sku_id},
    )
    conn.execute(
        text("""UPDATE core.mapping_queue SET status = 'confirmed'
                WHERE kind = 'sku' AND client_id = :c AND raw_code = :code"""),
        {"c": client_id, "code": raw_code},
    )
    return sku_id
