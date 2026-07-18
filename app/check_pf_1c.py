"""Сверка план-факта с 1С: Sell-In шт Q1 2026 (их «факт» vs наш 1С), по клиентам. Матч по токенам имени.
Запуск: docker compose exec -T app python -m app.check_pf_1c
"""
import re

import pandas as pd
from sqlalchemy import text

from .config import get_engine


def toks(s):
    s = re.sub(r"\(.*?\)", "", str(s)).lower().replace("ё", "е")
    return set(w for w in re.findall(r"[а-яa-z0-9]+", s) if len(w) > 3)


def main():
    eng = get_engine()
    pf = pd.read_sql(text(
        "SELECT client, SUM(fact) f FROM core.fact_plan_fact "
        "WHERE metric='Sell In, шт' AND period_label='1Q26' GROUP BY 1"), eng)
    c1 = pd.read_sql(text(
        "SELECT dc.group_name grp, SUM(f.qty) q FROM core.fact_sellin f "
        "JOIN core.dim_client dc ON dc.client_id=f.client_id "
        "WHERE f.period>='2026-01-01' AND f.period<'2026-04-01' GROUP BY 1"), eng)
    c1map = {r["grp"]: float(r["q"]) for _, r in c1.iterrows()}
    c1toks = {g: toks(g) for g in c1map}

    print(f"{'Клиент (план-факт)':<26}{'план-факт Q1':>13}{'1С Q1':>11}{'разница':>10}")
    print("-" * 60)
    tot_pf = tot_c1 = 0.0
    for _, r in pf.iterrows():
        pt = toks(r["client"])
        best, sc = None, 0
        for g, gt in c1toks.items():
            n = len(pt & gt)
            if n > sc:
                sc, best = n, g
        c1v = c1map.get(best) if sc else None
        pfv = float(r["f"] or 0)
        diff = f"{100*(pfv-c1v)/c1v:+.0f}%" if c1v else "нет в 1С"
        print(f"{r['client']:<26}{pfv:>13,.0f}{(c1v or 0):>11,.0f}{diff:>10}")
        tot_pf += pfv
        tot_c1 += (c1v or 0)
    print("-" * 60)
    print(f"{'ИТОГО':<26}{tot_pf:>13,.0f}{tot_c1:>11,.0f}"
          f"{(100*(tot_pf-tot_c1)/tot_c1 if tot_c1 else 0):>+9.0f}%")


if __name__ == "__main__":
    main()
