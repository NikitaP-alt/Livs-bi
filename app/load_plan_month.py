"""Загрузка ПОМЕСЯЧНОГО план-факта (зад.9) из Sales Retail, лист «SI-SO-ST».

Грейн листа: строка = Канал·Кол-воТТ·Дистр·Сеть·КАМ·Показатель·Период(год/тип) × 12 колонок месяцев (1..12).
Период кодирует год И тип: «2026 план» / «2026 факт» / «2026 форкаст» / «2025 план» / «2025 факт» / голый «2024».
Грузим только осмысленные метки (см. PERIOD_MAP); служебные (EVO, Форкаст/факт) пропускаем.
Дубликатов (Сеть×Показатель×Период) в листе нет (проверено). Запуск: docker compose exec -T app python -m app.load_plan_month
"""
import pandas as pd
from sqlalchemy import text

from .config import get_engine

FILE = "incoming/план/Sales Retail.xlsx"
SHEET = "SI-SO-ST"
SRC = "Sales Retail.xlsx#SI-SO-ST"
HDR = 2          # строка заголовка (месяцы 1..12 в колонках 7..18)
M0 = 7           # колонка месяца 1

# метка периода -> (год, тип)
PERIOD_MAP = {
    "2024": (2024, "факт"), "2025": (2025, "факт"), "2026": (2026, "факт"), "2027": (2027, "план"),
    "2025 план": (2025, "план"), "2025 факт": (2025, "факт"),
    "2026 план": (2026, "план"), "2026 факт": (2026, "факт"), "2026 форкаст": (2026, "форкаст"),
}


def _num(v):
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan") or "REF" in s or "DIV" in s:
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    d = pd.read_excel(FILE, sheet_name=SHEET, header=None, dtype=str).fillna("")
    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM core.fact_plan_month WHERE source_file=:f"), {"f": SRC})
        n = 0
        for r in range(HDR + 1, d.shape[0]):
            client = str(d.iloc[r, 3]).strip()
            metric = str(d.iloc[r, 5]).strip()
            period = str(d.iloc[r, 6]).strip()
            if not client or not metric or period not in PERIOD_MAP:
                continue
            year, kind = PERIOD_MAP[period]
            channel = str(d.iloc[r, 0]).strip()
            kam = str(d.iloc[r, 4]).strip()
            for m in range(1, 13):
                val = _num(d.iloc[r, M0 + m - 1])
                if val is None:
                    continue
                conn.execute(text(
                    "INSERT INTO core.fact_plan_month(channel,client,kam,metric,year,kind,month_num,value,source_file) "
                    "VALUES(:ch,:cl,:kam,:me,:y,:k,:m,:v,:f) ON CONFLICT DO NOTHING"),
                    {"ch": channel, "cl": client, "kam": kam, "me": metric,
                     "y": year, "k": kind, "m": m, "v": val, "f": SRC})
                n += 1
    print(f"помесячный план-факт загружен: {n} значений")


if __name__ == "__main__":
    main()
