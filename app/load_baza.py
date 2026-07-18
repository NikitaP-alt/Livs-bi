"""Обогащение города точек из файлов «База клиентов» (Фаза 2).
Соц.аптека: префикс кода -> город (из адреса файла). Диалог: нормализованный код -> Город (колонка файла).
Ригла (нет точек) и Вита (мусорные коды) — не сматчить, пропускаем.
Запуск: docker compose exec -T app python -m app.load_baza
"""
import re

import pandas as pd
from sqlalchemy import text

from .config import get_engine
from .enrich_city import find_city

SOC = "incoming/отчеты/Социальная аптека (Фармацевт)/База клиентов/Список Соц аптека Ливс_ с ИНН.xlsx"
DIA = "incoming/отчеты/Диалог/База клиентов/Диалог_База клиентов_08.25.xlsx"


def norm(s):
    s = str(s).strip().lower().replace("ё", "е")
    return re.sub(r"\d+$", "", s)


def main():
    eng = get_engine()
    with eng.begin() as conn:
        # --- Соц.аптека: префикс кода -> город ---
        f = pd.read_excel(SOC, header=3, dtype=str).fillna("")
        votes = {}
        for _, r in f.iterrows():
            code = str(r.iloc[0]).strip()
            if "-" not in code:
                continue
            city = find_city(str(r.iloc[2]))
            if city:
                votes.setdefault(code.split("-")[0], {}).setdefault(city, 0)
                votes[code.split("-")[0]][city] += 1
        pref = {p: max(cc, key=cc.get) for p, cc in votes.items()}
        cid = conn.execute(text("SELECT client_id FROM core.dim_client WHERE name='Социальная аптека'")).scalar()
        n_soc = 0
        for tt_id, code in conn.execute(text(
                "SELECT tt_id, client_tt_code FROM core.dim_tt WHERE client_id=:c AND (city IS NULL OR city='')"),
                {"c": cid}).fetchall():
            city = pref.get(str(code).split("-")[0])
            if city:
                conn.execute(text("UPDATE core.dim_tt SET city=:ci WHERE tt_id=:t"), {"ci": city, "t": tt_id})
                n_soc += 1

        # --- Диалог: нормализованный код -> Город ---
        fd = pd.read_excel(DIA, header=0, dtype=str).fillna("")
        c2c = {}
        for _, r in fd.iterrows():
            code, city = norm(r.iloc[0]), str(r.iloc[2]).strip()
            if code and city:
                c2c[code] = city
        cidd = conn.execute(text("SELECT client_id FROM core.dim_client WHERE name='Диалог'")).scalar()
        n_dia = 0
        for tt_id, code in conn.execute(text(
                "SELECT tt_id, client_tt_code FROM core.dim_tt WHERE client_id=:c AND (city IS NULL OR city='')"),
                {"c": cidd}).fetchall():
            city = c2c.get(norm(code))
            if city:
                conn.execute(text("UPDATE core.dim_tt SET city=:ci WHERE tt_id=:t"), {"ci": city, "t": tt_id})
                n_dia += 1

    print(f"Соц.аптека: город проставлен {n_soc}; Диалог: {n_dia}. "
          f"(префиксов Соц.аптеки: {len(pref)})")


if __name__ == "__main__":
    main()
