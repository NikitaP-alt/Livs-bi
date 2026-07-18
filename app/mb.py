"""Хелперы Metabase API: логин, upsert карточек/дашбордов, field-filter'ы для фильтров.

Используется скриптами build_*_dashboard.py. Идемпотентно (по имени карточки/дашборда).
"""
import os
import uuid

import requests

MB = os.environ.get("MB_URL", "http://metabase:3000")
USER = os.environ.get("MB_USER", "")          # задаётся в .env (вне git)
PWD = os.environ.get("MB_PASSWORD", "")        # задаётся в .env (вне git)
DB = int(os.environ.get("MB_DB", "2"))


def client():
    s = requests.Session()
    s.headers["X-Metabase-Session"] = s.post(
        f"{MB}/api/session", json={"username": USER, "password": PWD}).json()["id"]
    return s


def sync(s):
    s.post(f"{MB}/api/database/{DB}/sync_schema")


def field_ids(s, schema, table):
    """{имя_колонки: field_id} для витрины schema.table."""
    m = s.get(f"{MB}/api/database/{DB}/metadata", params={"include_hidden": "true"}).json()
    for tb in m["tables"]:
        if tb["schema"] == schema and tb["name"] == table:
            return {f["name"]: f["id"] for f in tb["fields"]}
    return {}


def set_list(s, field_id):
    """Показывать значения поля выпадающим списком в фильтре дашборда."""
    s.put(f"{MB}/api/field/{field_id}", json={"has_field_values": "list"})


def dim_tag(name, display, field_id, widget):
    """Template-tag типа field-filter (dimension) для нативного SQL ({{name}} -> 1=1 если пусто)."""
    return {name: {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "livs-" + name)),
                   "name": name, "display-name": display, "type": "dimension",
                   "dimension": ["field", field_id, None], "widget-type": widget}}


def param(pid, name, slug, ptype, section):
    return {"id": pid, "name": name, "slug": slug, "type": ptype, "sectionId": section}


def pmap(pid, card_id, tag):
    return {"parameter_id": pid, "card_id": card_id,
            "target": ["dimension", ["template-tag", tag]]}


def upsert_card(s, name, display, sql, viz=None, tags=None):
    existing = {c["name"]: c for c in s.get(f"{MB}/api/card").json() if not c.get("archived")}
    body = {"name": name, "display": display, "visualization_settings": viz or {},
            "dataset_query": {"type": "native", "database": DB,
                              "native": {"query": sql, "template-tags": tags or {}}}}
    if name in existing:
        cid = existing[name]["id"]
        s.put(f"{MB}/api/card/{cid}", json=body)
    else:
        cid = s.post(f"{MB}/api/card", json=body).json()["id"]
    return cid


def upsert_dashboard(s, name, dashcards, parameters):
    dashes = {d["name"]: d for d in s.get(f"{MB}/api/dashboard").json() if not d.get("archived")}
    did = dashes[name]["id"] if name in dashes else \
        s.post(f"{MB}/api/dashboard", json={"name": name}).json()["id"]
    s.put(f"{MB}/api/dashboard/{did}", json={"dashcards": dashcards, "parameters": parameters})
    return did
