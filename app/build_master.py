"""Черновая сборка мастер-товаров: классифицирует провизорные SKU (по названию)
в канонические товары ЛИВС и связывает dim_sku.product_id -> dim_product.

Запуск:  docker compose exec -T app python -m app.build_master
Группировка печатается для ручной проверки. Повторный запуск идемпотентен.
"""
from sqlalchemy import text
from .config import get_engine

PRODUCTS = {
    "D3_2000": "Витамин D3 2000МЕ (взрослый)",
    "D3_KIDS": "Витамин D3 для детей",
    "VITC_ZINC": "Витамин С + Цинк",
    "VITC_KIDS": "Витамин С для детей",
    "VITC_COMPLEX": "Витамин С Комплекс",
    "MAG_ADULT": "Магний Цитрат (взрослый)",
    "MAG_KIDS": "Магний Цитрат для детей",
    "OMEGA_ADULT": "Омега-3",
    "OMEGA_KIDS": "Омега-3 для детей",
    "IRON_ADULT": "Железо Плюс / Мультивитамины+Железо",
    "IRON_KIDS": "Железо Плюс для детей",
    "MULTI_KIDS": "Мультивитамины для детей",
    "MULTI_WOMEN": "Мультивитамины для женщин",
    "MULTI_MEN": "Мультивитамины для мужчин",
    "MEGA_KIDS": "Мега Мультивитамины для детей",
    "IMMUN_PLUS": "Иммун Плюс (С/D/Цинк)",
    "IMMUN_SYSTEM": "Иммун Систем (бузина/прополис/эхинацея)",
    "CALCIUM": "Кальций + D3",
    "BEAUTY": "Витамины Кожа/Волосы/Ногти",
    "BVIT_C": "Витамины группы B + C (Energy)",
    "PRENATAL": "Пренатал для беременных",
    "FOLIC": "Фолиевая кислота",
    "CURCUMIN": "Куркумин и Имбирь",
    "EYE": "Здоровье Глаз",
    "ELECTRO": "Комплекс Электролитов",
    "UNKNOWN": "❓ Не классифицировано",
}


def classify(name: str) -> str:
    s = name.lower().replace("ё", "е")
    kids = "дет" in s
    # узкоспецифичные
    if "пренатал" in s or "берем" in s:
        return "PRENATAL"
    if "фолиев" in s:
        return "FOLIC"
    if "куркумин" in s or "имбирь" in s:
        return "CURCUMIN"
    if "электролит" in s:
        return "ELECTRO"
    if "глаз" in s or "eye care" in s:
        return "EYE"
    if "кальци" in s:
        return "CALCIUM"
    if "омега" in s:
        return "OMEGA_KIDS" if kids else "OMEGA_ADULT"
    if "магни" in s:
        return "MAG_KIDS" if kids else "MAG_ADULT"
    if "желез" in s:
        return "IRON_KIDS" if kids else "IRON_ADULT"
    if "для детей с 3 лет" in s and "омега" not in s:
        return "MULTI_KIDS"
    if "мега" in s:
        return "MEGA_KIDS"
    if "иммун" in s or "имун" in s:
        if "эхинац" in s or "прополис" in s:
            return "IMMUN_SYSTEM"
        if "цинк" in s or "zn" in s:
            return "IMMUN_PLUS"
        return "IMMUN_SYSTEM"
    if "кож" in s or "волос" in s or "ногт" in s or "бьюти" in s:
        return "BEAUTY"
    if ("группы в" in s or "витамины в +" in s or "в,с" in s or "энерджи" in s
            or "в+вит" in s or "в+ вит" in s or "в плюс вит" in s or "гр. в" in s
            or "гр в плюс" in s or "гр.в" in s):
        return "BVIT_C"
    if ("витамин с" in s or "витамин-с" in s or "вит.с" in s or "вит с" in s
            or "витамины с" in s or "vitamin c" in s or "витамин c" in s or "вит c" in s
            or "с+цинк" in s or "c+цинк" in s or "с компл" in s or "c компл" in s
            or "с-компл" in s or "c-компл" in s):
        if "цинк" in s:
            return "VITC_ZINC"
        if kids:
            return "VITC_KIDS"
        return "VITC_COMPLEX"
    if "d3" in s or "д3" in s or "витамин-д" in s or "витамин д" in s or "vitamin d" in s:
        return "D3_KIDS" if kids else "D3_2000"
    if "мультивит" in s:
        if "женщ" in s or "жен." in s or "д/жен" in s:
            return "MULTI_WOMEN"
        if "мужч" in s or "муж." in s or "д/муж" in s:
            return "MULTI_MEN"
        if kids:
            return "MULTI_KIDS"
    return "UNKNOWN"


def main() -> None:
    eng = get_engine()
    with eng.begin() as conn:
        # создать/обновить мастер-товары
        key_to_id = {}
        for key, nm in PRODUCTS.items():
            pid = conn.execute(text(
                """INSERT INTO core.dim_product(code, name) VALUES (:c, :n)
                   ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name RETURNING product_id"""),
                {"c": key, "n": nm}).scalar_one()
            key_to_id[key] = pid

        skus = conn.execute(text("SELECT sku_id, name FROM core.dim_sku")).fetchall()
        groups: dict[str, list] = {}
        for sku_id, name in skus:
            key = classify(name or "")
            conn.execute(text("UPDATE core.dim_sku SET product_id=:p WHERE sku_id=:s"),
                         {"p": key_to_id[key], "s": sku_id})
            groups.setdefault(key, []).append(name)

    # печать группировки для проверки
    for key in PRODUCTS:
        names = groups.get(key, [])
        if not names:
            continue
        print(f"\n=== {PRODUCTS[key]}  ({len(names)}) ===")
        for n in sorted(names):
            print("   ", n)


if __name__ == "__main__":
    main()
