"""Прогноз продаж/закупок (зад.7). Метод: run-rate (ср. уровень 12 мес) × сезонный индекс месяца.
Простой и объяснимый, без ML. По ИТОГО и сетям, горизонт до конца 2027.
Запуск: docker compose exec -T app python -m app.build_forecast
"""
from statistics import mean

import pandas as pd
from sqlalchemy import text

from .config import get_engine

# metric -> SQL, дающий (year, month, grp, qty)
QUERIES = {
    "Продажи": """SELECT EXTRACT(YEAR FROM f.period)::int y, EXTRACT(MONTH FROM f.period)::int m,
                         dc.group_name grp, SUM(f.qty) qty
                  FROM core.fact_sellout f JOIN core.dim_client dc ON dc.client_id=f.client_id
                  WHERE dc.group_name IS NOT NULL GROUP BY 1,2,3""",
    "Закупки": """SELECT EXTRACT(YEAR FROM f.period)::int y, EXTRACT(MONTH FROM f.period)::int m,
                         dc.group_name grp, SUM(f.qty) qty
                  FROM core.fact_sellin f JOIN core.dim_client dc ON dc.client_id=f.client_id
                  WHERE dc.group_name IS NOT NULL GROUP BY 1,2,3""",
}


def add_months(y, m, k):
    idx = y * 12 + (m - 1) + k
    return idx // 12, idx % 12 + 1


SKIP_RECENT = 2   # последние 2 месяца приходят с лагом (неполные) -> считаем прогнозом, не фактом


def forecast(hist):
    """hist: {(y,m): value} -> (факты, прогноз). Последние SKIP_RECENT мес. -> в прогноз (неполные)."""
    keys = sorted(k for k, v in hist.items() if v)
    if len(keys) < 6:
        return {k: hist[k] for k in keys}, {}
    # уровень и сезонность — по ВСЕЙ истории (неполные последние мес. тянут уровень к реальному = самокоррекция)
    overall = mean([hist[k] for k in keys]) or 1
    bym = {}
    for (y, m) in keys:
        bym.setdefault(m, []).append(hist[(y, m)])
    si = {m: (mean(vs) / overall) for m, vs in bym.items()}
    level = mean([hist[k] for k in keys[-12:]])        # run-rate (вкл. неполные -> к текущему уровню)
    # но факты показываем без последних неполных месяцев — их отдаём прогнозом
    complete = keys[:-SKIP_RECENT] if len(keys) > SKIP_RECENT + 6 else keys
    facts = {k: hist[k] for k in complete}
    ly, lm = sorted(facts)[-1]
    out, k = {}, 1
    while k <= 30:                                     # прогноз включает недобранные последние месяцы + будущее
        y, m = add_months(ly, lm, k)
        if y > 2027 or (y == 2027 and m > 12):
            break
        out[(y, m)] = max(level * si.get(m, 1.0), 0)
        k += 1
    return facts, out


def main():
    eng = get_engine()
    rows = []
    for metric, sql in QUERIES.items():
        df = pd.read_sql(text(sql), eng)
        # ИТОГО + по каждой группе с достаточной историей
        scopes = {"ИТОГО": df.groupby(["y", "m"])["qty"].sum().to_dict()}
        for grp, g in df.groupby("grp"):
            h = g.groupby(["y", "m"])["qty"].sum().to_dict()
            if len([1 for v in h.values() if v]) >= 12:      # только группы с ≥12 мес
                scopes[grp] = h
        for scope, hist in scopes.items():
            facts, fc = forecast(hist)
            for (y, m), v in facts.items():
                rows.append((metric, scope, f"{y}-{m:02d}-01", float(v or 0), "факт"))
            for (y, m), v in fc.items():
                rows.append((metric, scope, f"{y}-{m:02d}-01", float(v), "прогноз"))

    with eng.begin() as conn:
        conn.execute(text("TRUNCATE core.fact_forecast"))
        conn.execute(text("INSERT INTO core.fact_forecast(metric,scope,period,value,kind) "
                          "VALUES(:me,:sc,:pe,:va,:ki)"),
                     [{"me": a, "sc": b, "pe": c, "va": d, "ki": e} for a, b, c, d, e in rows])
    fc = sum(1 for r in rows if r[4] == "прогноз")
    print(f"прогноз: {len(rows)} строк ({fc} прогнозных), сетей+ИТОГО по 2 метрикам")


if __name__ == "__main__":
    main()
