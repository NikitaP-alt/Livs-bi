"""Загрузка утверждённого прайса из «Ценовая политика LIVS» (лист «Аптеки (ком)»).

Первый блок листа = каноничный прайс: ID(6835xxx) · англ.наименование · Цена с НДС (Прайс
Базовый ПП, col4) · РРЦ (col6). Берём ПЕРВОЕ вхождение каждого ID (ниже идут поклиентские
блоки со скидками — их игнорируем). Маппим ID -> мастер-товар (core.dim_product.code) и грузим
в core.dim_product_price. Цена с НДС = закупка = Sell-In (по определению руководителя).

Нужен, чтобы посчитать Sell-Out в рублях там, где отчёт содержит только штуки (Диалог и др.).
Запуск: docker compose exec -T app python -m app.load_price_policy
"""
import pandas as pd
from sqlalchemy import text

from .config import get_engine

FILE = "incoming/план/Ценовая политика.xlsx"
SHEET = "Аптеки (ком)"

# ID из ценовой политики -> code мастер-товара (core.dim_product)
EXT2CODE = {
    "6835158":  "BVIT_C",        # ENERGY (B-COMPLEX)
    "6835186":  "IRON_ADULT",    # IRON PLUS
    "6835160":  "MULTI_WOMEN",   # WOMEN'S MULTIVITAMIN
    "6835187":  "IMMUN_SYSTEM",  # IMMUNE SYSTEM
    "6835181":  "BEAUTY",        # BEAUTY PLUS (HAIR SKIN NAILS)
    "6835164":  "CALCIUM",       # CALCIUM + VITAMIN D
    "6835149":  "D3_2000",       # VITAMIN-D
    "6835180":  "VITC_ZINC",     # VITAMIN C & ZINC
    "6835161":  "MULTI_MEN",     # MEN'S MULTIVITAMIN
    "6835091":  "OMEGA_ADULT",   # OMEGA 3
    "6835815":  "MAG_ADULT",     # MAGNESIUM
    "6835159":  "MULTI_KIDS",    # CHILDREN'S MULTIVITAMIN
    "7835091":  "OMEGA_KIDS",    # OMEGA 3 FOR KIDS
    "7835815":  "MAG_KIDS",      # MAGNESIUM FOR KIDS
    "7835072":  "MEGA_KIDS",     # MEGA MULTIVITAMIN 60
    "7835186":  "IRON_KIDS",     # IRON PLUS FOR KIDS
    "68357130": "VITC_COMPLEX",  # Vitamin C Complex
    "68357630": "CURCUMIN",      # Curcumin & Ginger
    "68358050": "EYE",           # Eye Health
    "68357500": "VITC_KIDS",     # Vitamin C for kids
    "68357190": "D3_KIDS",       # Vitamin D3 for kids
    # 68358490 «Чебурашка» — отдельный лицензионный SKU, отдельного мастера нет -> пропуск
}
# Прайс-прокси: мастера, которых нет отдельной строкой в политике, но продажи есть.
# Берём цену другого мастера (approx=TRUE, помечаем в дашбордах как оценку).
PROXY = {
    "IMMUN_PLUS": "IMMUN_SYSTEM",   # Иммун Плюс (С/D/Цинк) — по цене Иммун Систем
}


def _num(v):
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def main():
    d = pd.read_excel(FILE, sheet_name=SHEET, header=None, dtype=str).fillna("")
    # первое вхождение каждого ID = каноничная строка прайса
    prices = {}   # ext_id -> (ext_name, price_vat, rrc)
    for r in range(4, d.shape[0]):
        ext = str(d.iloc[r, 1]).strip()
        if not ext.isdigit() or ext in prices:
            continue
        name = str(d.iloc[r, 2]).strip()
        price_vat = _num(d.iloc[r, 4])   # Цена с НДС (Прайс Базовый ПП)
        rrc = _num(d.iloc[r, 6])         # РРЦ
        prices[ext] = (name, price_vat, rrc)

    eng = get_engine()
    with eng.begin() as conn:
        codes = {c: pid for c, pid in conn.execute(
            text("SELECT code, product_id FROM core.dim_product"))}
        conn.execute(text("TRUNCATE core.dim_product_price"))
        n = 0
        rows = []
        # прямые соответствия
        for ext, code in EXT2CODE.items():
            if ext not in prices or code not in codes:
                continue
            name, pv, rrc = prices[ext]
            if pv is None:
                continue
            rows.append((codes[code], ext, name, pv, rrc, False))
        # прокси
        for code, src_code in PROXY.items():
            src_ext = next((e for e, c in EXT2CODE.items() if c == src_code), None)
            if code not in codes or src_ext is None or src_ext not in prices:
                continue
            name, pv, rrc = prices[src_ext]
            if pv is None:
                continue
            rows.append((codes[code], src_ext, f"{name} (прокси)", pv, rrc, True))
        for pid, ext, name, pv, rrc, approx in rows:
            conn.execute(text(
                "INSERT INTO core.dim_product_price(product_id,ext_id,ext_name,price_vat,rrc,approx) "
                "VALUES(:p,:e,:n,:pv,:rrc,:a)"),
                {"p": pid, "e": ext, "n": name, "pv": pv, "rrc": rrc, "a": approx})
            n += 1

    covered = {c for c in EXT2CODE.values()} | set(PROXY)
    missing = [c for c in codes if c not in covered and c not in ("UNKNOWN",)]
    print(f"Прайс загружен: {n} мастер-товаров (из них прокси: {len(PROXY)}).")
    print(f"Без прайса (останутся без рублей в Sell-Out): {sorted(missing)}")


if __name__ == "__main__":
    main()
