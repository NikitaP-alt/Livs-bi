"""Загрузка план-факта (зад.9) из «ПЛАН ФАКТ 2026» (листы Ритейл/E-com).
Клиент=colB (повторяется), Показатель=colC. По кварталам: план/факт(прогноз).
Запуск: docker compose exec -T app python -m app.load_plan_fact
"""
import pandas as pd
from sqlalchemy import text

from .config import get_engine

FILE = "incoming/план/ПЛАН ФАКТ 2026.xlsx"
SRC = "ПЛАН ФАКТ 2026.xlsx"
SHEETS = {"Ритейл 2026": "Ритейл", "E-com 2026": "E-com"}
METRICS = {"Sell In, руб", "Sell In, шт", "Sell Out, руб", "Sell Out, шт"}
# период -> (plan_col, fact_col, quarter)
PERIODS = [("1Q26", 6, 7, 1), ("2Q26", 10, 11, 2), ("3Q26", 14, 15, 3),
           ("4Q26", 18, 19, 4), ("2026", 22, 23, None)]


def _num(v):
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main():
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM core.fact_plan_fact WHERE source_file=:f"), {"f": SRC})
        n = 0
        for sheet, channel in SHEETS.items():
            d = pd.read_excel(FILE, sheet_name=sheet, header=None, dtype=str).fillna("")
            for r in range(3, d.shape[0]):
                client = str(d.iloc[r, 1]).strip()
                metric = str(d.iloc[r, 2]).strip()
                if not client or client.startswith("ИТОГО") or metric not in METRICS:
                    continue
                for label, pc, fc, q in PERIODS:
                    plan = _num(d.iloc[r, pc])
                    fact = _num(d.iloc[r, fc])
                    if plan is None and fact is None:
                        continue
                    conn.execute(text(
                        "INSERT INTO core.fact_plan_fact(client,channel,metric,period_label,quarter,plan,fact,source_file) "
                        "VALUES(:c,:ch,:m,:pl,:q,:plan,:fact,:f) ON CONFLICT DO NOTHING"),
                        {"c": client, "ch": channel, "m": metric, "pl": label, "q": q,
                         "plan": plan, "fact": fact, "f": SRC})
                    n += 1
    print(f"план-факт загружен: {n} строк")


if __name__ == "__main__":
    main()
