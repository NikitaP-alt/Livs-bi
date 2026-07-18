"""Реестр: имя папки клиента в incoming/отчеты -> чем грузить.

kind=py  -> app/adapters/custom/<ref>.py (функция adapt + CLIENT)
kind=yaml -> YAML-конфиг (движок base.adapt)
"""
REGISTRY = {
    # --- группа A / готовые ---
    "Диалог":          {"kind": "py",   "ref": "dialog",
                        "skip_files": r"2022-08-09|2022-08-10|22\.08-19\.09"},
    "еАптека":         {"kind": "yaml", "ref": "app/adapters/configs/eapteka.yaml"},
    "ПланетаЗдоровья": {"kind": "py",   "ref": "planeta"},
    "Аптека.ру":       {"kind": "yaml", "ref": "app/adapters/configs/apteka_ru.yaml"},
    "ЛекОптТорг (СПБ)": {"kind": "py", "ref": "lekopttorg", "skip_files": r"[Аа]кци"},
    "Социальная аптека (Фармацевт)": {"kind": "py", "ref": "sotsialnaya"},
    "Невис СПБ":       {"kind": "yaml", "ref": "app/adapters/configs/nevis.yaml"},
    "Фармаимпекс (Ижевск)": {"kind": "py", "ref": "farmaimpeks"},
    "Гармония Здоровья Красноярск": {"kind": "py", "ref": "garmonia",
                        "skip_files": r"Отчет|май-июнь|03\.24-04\.24"},
    # --- группа B / готовые ---
    "Вита (Томск)":    {"kind": "py",   "ref": "vita_tomsk"},
    # "Вита (Самара)" ОТКЛЮЧЕНА: новый широкий формат 2025-12+/2026 (3720 колонок)
    # ломает выбор колонки qty (берёт ID ~192027). Включить после доработки vita_samara.py.
    # "Вита (Самара)":   {"kind": "py",   "ref": "vita_samara"},
    "НеоФарм":         {"kind": "py",   "ref": "neofarm"},
    "Мелодия Здоровья (СПБ)": {"kind": "py", "ref": "melodiya_spb"},
    "Фармперспектива": {"kind": "py", "ref": "farmperspektiva"},
    "ЛюбимаяАптека (Тула)": {"kind": "py", "ref": "lyubimaya"},
    "Ригла": {"kind": "py", "ref": "rigla"},
}

# папки, которые батч-лоадер пропускает (справочники/спец — отдельная волна)
SKIP_DIR_PARTS = ["База клиентов", "ОСГ"]
