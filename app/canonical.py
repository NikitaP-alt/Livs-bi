"""Каноническая строка — единый вид, к которому переходники приводят любой отчёт."""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class SalesRow:
    source: str                      # sellout | stock | sellin | pos_purchase
    client_name: str
    sku_code: str                    # код/наименование товара в отчёте клиента
    qty: float
    sku_name: Optional[str] = None   # сырое наименование (для очереди сопоставлений)
    rub: Optional[float] = None
    tt_code: Optional[str] = None    # ключ точки внутри клиента (код или адрес)
    tt_name: Optional[str] = None
    tt_chain: Optional[str] = None   # аптечная сеть/юрлицо (атрибут точки)
    tt_city: Optional[str] = None
    tt_inn: Optional[str] = None     # ИНН юрлица точки
    period: Optional[date] = None        # месяц (1-е число) для sellin/sellout/pos_purchase
    snapshot_date: Optional[date] = None # дата снимка для stock
