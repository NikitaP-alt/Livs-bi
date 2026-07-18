"""Загрузка доходности клиента (зад.10) из «Sales Retail»: свод доходность + свод инвестиции.
Мёржим по нормализованному имени клиента. Запуск: docker compose exec -T app python -m app.load_dohodnost
"""
import pandas as pd
from sqlalchemy import text

from .config import get_engine

FILE = "incoming/план/Sales Retail.xlsx"
SRC = "Sales Retail.xlsx#свод"


def _num(v):
    s = str(v).strip().replace("\xa0", "").replace(" ", "").replace(",", ".")
    if s in ("", "-", "nan"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _norm(s):
    s = str(s).split("(")[0].strip().lower().replace("ё", "е")
    w = s.split()
    if not w:
        return s
    if w[0] in ("new", "нью"):     # New ТС 1 / NEW AC ... — не схлопывать по первому слову
        return " ".join(w)
    return w[0]


def main():
    inv = pd.read_excel(FILE, sheet_name="свод инвестиции", header=None, dtype=str).fillna("")
    doh = pd.read_excel(FILE, sheet_name="свод доходность", header=None, dtype=str).fillna("")

    invmap = {}
    for r in range(4, inv.shape[0]):
        client = str(inv.iloc[r, 0]).strip()
        if not client or _num(inv.iloc[r, 5]) is None:
            continue
        invmap[_norm(client)] = {
            "manager": str(inv.iloc[r, 1]).strip(), "channel": str(inv.iloc[r, 2]).strip(),
            "si25": _num(inv.iloc[r, 3]), "si26": _num(inv.iloc[r, 5]), "share": _num(inv.iloc[r, 7]),
            "premia": _num(inv.iloc[r, 8]), "promo": _num(inv.iloc[r, 9]), "paid": _num(inv.iloc[r, 10]),
            "cert": _num(inv.iloc[r, 11]), "samples": _num(inv.iloc[r, 12]), "isg": _num(inv.iloc[r, 13]),
            "invtot": _num(inv.iloc[r, 14])}

    rows = []
    for mc, cc, pc, fc, sc in [(0, 1, 2, 3, 4), (6, 7, 8, 9, 10)]:
        for r in range(2, doh.shape[0]):
            client = str(doh.iloc[r, cc]).strip()
            if not client or client == "Клиент" or client.startswith("ИТОГО"):
                continue
            plan = _num(doh.iloc[r, pc])
            if plan is None:
                continue
            rows.append({"client": client, "manager": str(doh.iloc[r, mc]).strip(),
                         "plan": plan, "forecast": _num(doh.iloc[r, fc]), "share": _num(doh.iloc[r, sc])})

    eng = get_engine()
    with eng.begin() as conn:
        conn.execute(text("DELETE FROM core.fact_client_econ WHERE source_file=:f"), {"f": SRC})
        n = matched = 0
        for d in rows:
            iv = invmap.get(_norm(d["client"]), {})
            if iv:
                matched += 1
            conn.execute(text("""INSERT INTO core.fact_client_econ
                (client,manager,channel,si_2025,si_2026_plan,share_si,premia,promo,paid_services,
                 certificates,samples,isg,invest_total,dohodnost_plan,dohodnost_forecast,source_file)
                VALUES(:c,:m,:ch,:si25,:si26,:sh,:pr,:pm,:pd,:ct,:sm,:isg,:it,:pl,:fc,:f)
                ON CONFLICT (client,source_file) DO NOTHING"""),
                {"c": d["client"], "m": d["manager"] or iv.get("manager"), "ch": iv.get("channel"),
                 "si25": iv.get("si25"), "si26": iv.get("si26"),
                 "sh": d["share"] if d["share"] is not None else iv.get("share"),
                 "pr": iv.get("premia"), "pm": iv.get("promo"), "pd": iv.get("paid"),
                 "ct": iv.get("cert"), "sm": iv.get("samples"), "isg": iv.get("isg"),
                 "it": iv.get("invtot"), "pl": d["plan"], "fc": d["forecast"], "f": SRC})
            n += 1
    print(f"доходность: {n} клиентов загружено, из них с инвестициями сматчено: {matched}")


if __name__ == "__main__":
    main()
