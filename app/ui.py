"""GUI загрузки отчётов (Streamlit).

Перетащи сырой Excel -> авто-переходник разбирает -> предпросмотр + проверка ->
«Загрузить в базу» (сразу видно в Metabase) / «Скачать единый шаблон».
Клиент выбирается из списка (или новый). Повторная загрузка месяца ЗАМЕНЯЕТ данные (без дублей).

Запуск: docker compose up -d ui  ->  http://localhost:8501
"""
import sys
sys.path.insert(0, "/code")

import io
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st
from sqlalchemy import text

from app.adapters import auto
from app import ingest, batch
from app.config import get_engine
from app.mapping import get_or_create_client

st.set_page_config(page_title="LIVS — Загрузка отчётов", layout="wide")
st.title("📥 LIVS BI — Загрузка отчёта сети")
st.caption("Перетащи сырой Excel — система разберёт формат, проверит и загрузит. "
           "После загрузки данные сразу появятся в дашборде Metabase.")

eng = get_engine()
with eng.begin() as conn:
    existing = [r[0] for r in conn.execute(text("SELECT name FROM core.dim_client ORDER BY name"))]

up = st.file_uploader("1) Перетащи отчёт (.xlsx / .xls)", type=["xlsx", "xls"])

c1, c2 = st.columns(2)
choice = c1.selectbox("2) Сеть (клиент)", ["— выбери —"] + existing + ["➕ Новая сеть…"])
new_name = c1.text_input("Название новой сети") if choice == "➕ Новая сеть…" else ""
cname = new_name.strip() if choice == "➕ Новая сеть…" else ("" if choice == "— выбери —" else choice)
period_in = c2.text_input("3) Период ГГГГ-ММ (если не указан в файле — оставь пусто)")

if up is not None:
    tmp = Path(tempfile.gettempdir()) / up.name
    tmp.write_bytes(up.getbuffer())
    period = period_in.strip() or batch.parse_period(Path(up.name))

    if not cname:
        st.warning("⚠️ Выбери сеть (клиента) выше — иначе данные не привязать.")
        st.stop()

    st.info(f"Сеть: **{cname}**  ·  период: **{period or 'из файла'}**  ·  файл: {up.name}")
    try:
        rows, raw = auto.adapt(str(tmp), period or None, cname)
    except Exception as e:
        st.error(f"Не удалось разобрать файл: {e}")
        st.stop()

    if not rows:
        st.warning("Строки не распознаны (нестандартный формат / не указан период / спец-отчёт).")
        st.stop()

    df = pd.DataFrame([{
        "факт": r.source, "товар": r.sku_name, "код точки": r.tt_code, "ИНН": r.tt_inn,
        "город": r.tt_city, "кол-во": r.qty, "период": r.period or r.snapshot_date,
    } for r in rows])
    st.success(f"Распознано строк: **{len(df)}**  ·  факты: {df['факт'].value_counts().to_dict()}")

    mx = pd.to_numeric(df["кол-во"], errors="coerce").max()
    if mx and mx > 5000:
        st.warning(f"⚠️ Подозрительно большое количество: **{int(mx)}**. "
                   "Проверь, не попал ли в «кол-во» ID или сумма.")

    st.subheader("Предпросмотр (первые 300 строк)")
    st.dataframe(df.head(300), use_container_width=True)

    b1, b2 = st.columns(2)
    if b1.button("✅ Загрузить в базу (заменит данные за этот месяц)", type="primary"):
        # ЗАМЕНА: удаляем прежние факты этой сети за те же периоды (чтобы не задвоить)
        per = defaultdict(set)
        for r in rows:
            if r.source == "stock" and r.snapshot_date:
                per["stock"].add(date(r.snapshot_date.year, r.snapshot_date.month, 1))
            elif r.period:
                per[r.source].add(r.period)
        with eng.begin() as conn:
            cid = get_or_create_client(conn, cname)
            for src, pers in per.items():
                if src == "stock":
                    conn.execute(text("DELETE FROM core.fact_stock WHERE client_id=:c "
                                      "AND date_trunc('month',snapshot_date)::date = ANY(:p)"),
                                 {"c": cid, "p": list(pers)})
                else:
                    conn.execute(text(f"DELETE FROM core.fact_{src} WHERE client_id=:c "
                                      "AND period = ANY(:p)"), {"c": cid, "p": list(pers)})
        summ = ingest._load_rows(SimpleNamespace(auto_sku=True), cname, rows, raw, up.name)
        st.success(f"✅ Загружено: {summ}. Открой Metabase — данные уже на дашборде.")

        # --- АВТОПРОВЕРКА КАЧЕСТВА сразу после загрузки ---
        st.subheader("🔎 Проверка данных")

        def _prev(p):
            return date(p.year - 1, 12, 1) if p.month == 1 else date(p.year, p.month - 1, 1)

        issues = []
        with eng.begin() as conn:
            cid2 = conn.execute(text("SELECT client_id FROM core.dim_client WHERE name=:n"),
                                {"n": cname}).scalar()
            for src, pers in per.items():
                tbl = "fact_stock" if src == "stock" else f"fact_{src}"
                dcol = "snapshot_date" if src == "stock" else "period"
                for p in sorted(pers):
                    cur = conn.execute(text(f"SELECT COALESCE(SUM(qty),0) FROM core.{tbl} "
                                            f"WHERE client_id=:c AND date_trunc('month',{dcol})::date=:p"),
                                       {"c": cid2, "p": p}).scalar()
                    prev = conn.execute(text(f"SELECT SUM(qty) FROM core.{tbl} "
                                             f"WHERE client_id=:c AND date_trunc('month',{dcol})::date=:p"),
                                        {"c": cid2, "p": _prev(p)}).scalar()
                    if prev and float(prev) > 0:
                        chg = 100 * (float(cur) - float(prev)) / float(prev)
                        if abs(chg) >= 50:
                            issues.append(f"📈 {src} за {p:%Y-%m}: {float(cur):,.0f} против "
                                          f"{float(prev):,.0f} в пред. месяце (**{chg:+.0f}%**) — резкий скачок, проверь")
                bad = conn.execute(text(f"SELECT COUNT(*) FROM core.{tbl} WHERE client_id=:c "
                                        "AND (qty>20000 OR qty<0)"), {"c": cid2}).scalar()
                if bad:
                    issues.append(f"🔴 {src}: {bad} строк с аномальным кол-вом (>20000 или <0) — "
                                  "похоже, в «кол-во» попал ID/сумма")
            unc = conn.execute(text("SELECT COUNT(*) FROM core.dim_sku WHERE product_id IS NULL")).scalar()
            if unc:
                issues.append(f"🟡 {unc} товаров без мастер-категории — прогони классификатор "
                              "(`docker compose exec app python -m app.build_master`)")

        if issues:
            for it in issues:
                st.warning(it)
            st.caption("Проверь подозрительное перед показом. Детали — дашборд «Проверка данных» в Metabase.")
        else:
            st.success("✅ Проверка пройдена: резких скачков и аномалий не найдено.")

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Единый шаблон")
    buf.seek(0)
    b2.download_button("⬇️ Скачать единый шаблон (Excel)", buf,
                       file_name=f"{cname}_единый_шаблон.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
