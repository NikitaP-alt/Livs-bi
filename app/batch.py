"""Батч-загрузка корпуса incoming/отчеты по реестру.

- выводит период из путей/имён (продажи_07.25, 20240311, «Май 2024», 2026.05);
- выбирает переходник клиента из registry;
- грузит каждый файл через ingest._load_rows (идемпотентность по относительному пути);
- ловит ошибки пофайлово и печатает сводку.

Запуск:
  docker compose exec -T app python -m app.batch                 # все из реестра
  docker compose exec -T app python -m app.batch "еАптека"       # один клиент
"""
from __future__ import annotations
import argparse
import importlib
import re
from pathlib import Path
from types import SimpleNamespace

from .adapters.base import load_config, adapt as yaml_adapt
from . import ingest
from .registry import REGISTRY, SKIP_DIR_PARTS

ROOT = Path("incoming/отчеты")
RU = {"январь": 1, "февраль": 2, "март": 3, "апрель": 4, "май": 5, "июнь": 6,
      "июль": 7, "август": 8, "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12}


def parse_period(path: Path):
    """Вернуть 'YYYY-MM' из имени/пути файла, либо None (тогда период берёт сам переходник)."""
    name = path.name
    low = str(path).lower()
    m = re.search(r"\b\d{2}\.(\d{2})\.(20\d{2})", name)        # DD.MM.YYYY (раньше MM.YY!)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = re.search(r"_(\d{2})\.(\d{2})(?:\D|$)", name)          # продажи_07.25 (MM.YY)
    if m:
        return f"20{m.group(2)}-{m.group(1)}"
    m = re.search(r"(20\d{2})[._-](\d{2})[._-]\d{2}", name)    # 2025_05_03 / 2025-05-03
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", name)            # 20240311_...
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"\b\d{2}\.(\d{2})\.(20\d{2})", name)        # на 10.07.2024 / с 01.05.2024
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    for w, mo in RU.items():                                    # «Май 2024» или «2024_май» (рядом)
        mm = re.search(w + r"\D{0,4}(20\d{2})", low) or re.search(r"(20\d{2})\D{0,4}" + w, low)
        if mm:
            return f"{mm.group(1)}-{mo:02d}"
    m = re.search(r"(20\d{2})[.\-](\d{2})(?:\D|$)", name)      # 2026.05 / 2024-05
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    nlow = name.lower()                                          # месяц словом в ИМЕНИ + год в ПУТИ/«22»
    for w, mo in RU.items():
        if re.search(r"\b" + w, nlow):
            yrs = re.findall(r"20\d{2}", str(path))
            if yrs:
                return f"{yrs[-1]}-{mo:02d}"
            y2 = re.search(w + r"[^0-9]{0,3}(\d{2})\b", nlow)
            if y2:
                return f"20{y2.group(1)}-{mo:02d}"
    return None


def get_adapter(client: str):
    reg = REGISTRY.get(client)
    if reg is None:                      # нет в реестре -> авто-переходник
        from .adapters import auto
        return (lambda f, p: auto.adapt(f, p, client)), client
    if reg["kind"] == "py":
        mod = importlib.import_module(f"app.adapters.custom.{reg['ref']}")
        return (lambda f, p: mod.adapt(f, p)), mod.CLIENT
    cfg = load_config(reg["ref"])
    return (lambda f, p: yaml_adapt(cfg, f, p)), cfg["client"]


def iter_files(cdir: Path, skip_re: str | None = None):
    fs = [p for p in cdir.rglob("*.xlsx") if not p.name.startswith("~$")]
    fs += [p for p in cdir.rglob("*.xls") if not p.name.startswith("~$")]
    fs += [p for p in cdir.rglob("*.csv")]
    fs = [f for f in sorted(fs) if not any(s in str(f) for s in SKIP_DIR_PARTS)]
    if skip_re:
        fs = [f for f in fs if not re.search(skip_re, f.name)]
    return fs


def load_client(client: str, auto_sku: bool = True):
    adapter, client_name = get_adapter(client)
    cdir = ROOT / client
    files = iter_files(cdir, REGISTRY.get(client, {}).get("skip_files"))
    args = SimpleNamespace(auto_sku=auto_sku)
    ok, fail, tot = 0, [], {}
    for f in files:
        rel = str(f.relative_to(ROOT))
        try:
            rows, raw = adapter(str(f), parse_period(f))
            summ = ingest._load_rows(args, client_name, rows, raw, rel)
            ok += 1
            for src, (loaded, _q) in summ.items():
                tot[src] = tot.get(src, 0) + loaded
        except Exception as e:
            fail.append((rel, str(e).replace("\n", " ")[:160]))
    print(f"[{client}] файлов: {len(files)} | ок: {ok} | ошибок: {len(fail)} | загружено: {tot}")
    for rel, err in fail[:20]:
        print(f"   FAIL {rel}: {err}")
    return ok, fail


def main():
    ap = argparse.ArgumentParser(prog="app.batch")
    ap.add_argument("clients", nargs="*", help="папки клиентов; пусто = все из реестра")
    ap.add_argument("--no-auto-sku", action="store_true")
    ap.add_argument("--all-folders", action="store_true",
                    help="обойти ВСЕ папки клиентов (реестр где есть, иначе авто-переходник)")
    a = ap.parse_args()
    if a.all_folders:
        targets = sorted(d.name for d in ROOT.iterdir() if d.is_dir())
    else:
        targets = a.clients or list(REGISTRY.keys())
    for c in targets:
        if not (ROOT / c).is_dir():
            print(f"[{c}] папка не найдена — пропуск")
            continue
        load_client(c, auto_sku=not a.no_auto_sku)


if __name__ == "__main__":
    main()
