"""Создать view-only пользователя Metabase + сделать не-админов «только просмотр».

- «All Users» -> коллекция LIVS BI (5) = read; create-queries = no (нельзя строить/править запросы),
  view-data остаётся (дашборды рендерятся), download = full (можно выгружать в Excel).
- Администраторы (это ты) не затрагиваются — правят всё.
Запуск: docker compose exec -T app python -m app.mb_viewer
"""
import os

from . import mb

VIEWER_EMAIL = os.environ.get("MB_VIEWER_EMAIL", "viewer@livs.local")
VIEWER_PASS = os.environ.get("MB_VIEWER_PASS", "")   # задаётся в .env (вне git)
COLL = 5      # коллекция LIVS BI
DB = 2        # база LIVS
ALLUSERS = 1  # группа All Users


def main():
    s = mb.client()

    # 1) коллекция LIVS BI: All Users -> read (было write)
    cg = s.get(f"{mb.MB}/api/collection/graph").json()
    s.put(f"{mb.MB}/api/collection/graph",
          json={"revision": cg["revision"], "groups": {str(ALLUSERS): {str(COLL): "read"}}})
    print("коллекция LIVS BI: All Users понижены до 'read'")

    # 2) данные: All Users -> нельзя строить запросы (но дашборды видит + выгрузка)
    pg = s.get(f"{mb.MB}/api/permissions/graph").json()
    block = pg["groups"][str(ALLUSERS)][str(DB)]
    block["create-queries"] = "no"
    block["view-data"] = "unrestricted"
    s.put(f"{mb.MB}/api/permissions/graph",
          json={"revision": pg["revision"], "groups": {str(ALLUSERS): {str(DB): block}}})
    print("данные: All Users -> create-queries=no (только просмотр)")

    # 3) создать пользователя (не админ)
    users = {u["email"]: u for u in s.get(f"{mb.MB}/api/user").json().get("data", [])}
    if VIEWER_EMAIL in users:
        uid = users[VIEWER_EMAIL]["id"]
        print(f"пользователь уже есть, id={uid}")
    else:
        r = s.post(f"{mb.MB}/api/user", json={
            "first_name": "Просмотр", "last_name": "LIVS",
            "email": VIEWER_EMAIL, "password": VIEWER_PASS,
            "user_group_memberships": [{"id": ALLUSERS}]})
        j = r.json()
        uid = j.get("id")
        print(f"создан пользователь id={uid} (ответ: {list(j.keys())})")

    # 4) проверка входа под вьюером
    try:
        s2 = mb.requests.Session()
        tok = s2.post(f"{mb.MB}/api/session",
                      json={"username": VIEWER_EMAIL, "password": VIEWER_PASS}).json().get("id")
        if tok:
            s2.headers["X-Metabase-Session"] = tok
            me = s2.get(f"{mb.MB}/api/user/current").json()
            print(f"ВХОД OK: {me.get('email')}  admin={me.get('is_superuser')}")
        else:
            print("ВХОД НЕ УДАЛСЯ — пароль не установился, нужен ручной сброс")
    except Exception as e:
        print("проверка входа: ошибка", e)

    print(f"\nЛогин view-only: {VIEWER_EMAIL} / {VIEWER_PASS}")


if __name__ == "__main__":
    main()
