"""Обслуживание Metabase: инвентаризация БД/дашбордов + health-check всех карточек.

Только ЧТЕНИЕ (ничего не меняет). Запуск: docker compose exec -T app python -m app.mb_maint
"""
from . import mb


def main():
    s = mb.client()

    print("=== БАЗЫ ДАННЫХ ===")
    for d in s.get(f"{mb.MB}/api/database").json().get("data", []):
        print(f"  id={d['id']:>3}  {d['name']!r}  engine={d.get('engine')}")

    print("\n=== ДАШБОРДЫ ===")
    dashes = [d for d in s.get(f"{mb.MB}/api/dashboard").json() if not d.get("archived")]
    for d in sorted(dashes, key=lambda x: x["id"]):
        print(f"  id={d['id']:>3}  {d['name']!r}  collection={d.get('collection_id')}")

    print("\n=== HEALTH-CHECK КАРТОЧЕК (по дашбордам) ===")
    broken = 0
    for d in sorted(dashes, key=lambda x: x["id"]):
        full = s.get(f"{mb.MB}/api/dashboard/{d['id']}").json()
        bad = []
        for dc in full.get("dashcards", []):
            cid = dc.get("card_id")
            if not cid:
                continue
            r = s.post(f"{mb.MB}/api/card/{cid}/query/json", json={"parameters": []})
            try:
                j = r.json()
            except Exception:
                bad.append((cid, "нет JSON"))
                continue
            if isinstance(j, dict) and (j.get("error") or j.get("status") == "failed"):
                bad.append((cid, str(j.get("error"))[:80]))
        if bad:
            broken += len(bad)
            print(f"  ⚠ Дашборд {d['id']} «{d['name']}»:")
            for cid, err in bad:
                print(f"      карточка {cid}: {err}")
        else:
            print(f"  ✓ Дашборд {d['id']} «{d['name']}» — все карточки ок")
    print(f"\nИТОГО сломанных карточек: {broken}")


if __name__ == "__main__":
    main()
