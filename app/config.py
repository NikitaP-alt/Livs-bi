"""Подключение к БД из переменной окружения DATABASE_URL."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def get_engine() -> Engine:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL не задан. Пример: "
            "postgresql+psycopg2://livs:change_me@db:5432/livs_bi"
        )
    return create_engine(url, future=True)
