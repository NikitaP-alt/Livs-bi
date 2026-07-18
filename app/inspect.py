"""Осмотр Excel-файла: листы, сырые верхние строки, чтобы понять структуру шапки.

Запуск (в контейнере):
  docker compose exec -T app python -m app.inspect incoming/файл.xlsx
  docker compose exec -T app python -m app.inspect "incoming/*.xlsx"
"""
import sys
from pathlib import Path

import pandas as pd


def inspect(path: Path, n: int = 15) -> None:
    print(f"\n===== {path.name} =====")
    try:
        from .adapters.auto import _fix_xlsx
        xl = pd.ExcelFile(_fix_xlsx(str(path)))
    except Exception as e:
        print(f"  не открыть: {e}")
        return
    print("Листы:", xl.sheet_names)
    for sh in xl.sheet_names:
        df = xl.parse(sh, header=None, nrows=n, dtype=str).fillna("")
        print(f"\n--- Лист '{sh}': первые {n} строк (БЕЗ интерпретации заголовка) ---")
        print(f"колонок прочитано: {df.shape[1]}")
        with pd.option_context("display.max_columns", None,
                               "display.width", 220,
                               "display.max_colwidth", 28):
            print(df.to_string(index=True, header=True))


def main() -> None:
    if len(sys.argv) < 2:
        print("укажи путь к файлу или маску, напр. incoming/*.xlsx")
        return
    for arg in sys.argv[1:]:
        paths = sorted(Path(".").glob(arg)) if any(c in arg for c in "*?[") else [Path(arg)]
        if not paths:
            print(f"нет файлов по: {arg}")
        for p in paths:
            inspect(p)


if __name__ == "__main__":
    main()
