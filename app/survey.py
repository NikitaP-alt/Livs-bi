"""Разведка форматов: по одному репрезентативному файлу с каждого клиента —
листы и заголовки (первые строки). Нужна, чтобы сгруппировать клиентов по форматам.

Запуск: docker compose exec -T app python -m app.survey
"""
from pathlib import Path
import pandas as pd

ROOT = Path("incoming/отчеты")


def header_guess(df: pd.DataFrame) -> list:
    # ищем в первых 6 строках строку с максимумом непустых ячеек
    best_i, best_n = 0, -1
    for i in range(min(len(df), 6)):
        n = sum(1 for x in df.iloc[i].tolist() if str(x).strip())
        if n > best_n:
            best_i, best_n = i, n
    return [str(x).strip() for x in df.iloc[best_i].tolist() if str(x).strip()][:12]


def main() -> None:
    clients = sorted([d for d in ROOT.iterdir() if d.is_dir()])
    print(f"Клиентов: {len(clients)}\n")
    for cd in clients:
        files = [p for p in cd.rglob("*.xlsx") if not p.name.startswith("~$")]
        files += [p for p in cd.rglob("*.xls") if not p.name.startswith("~$")]
        if not files:
            print(f"### {cd.name}: нет файлов\n")
            continue
        pref = [f for f in files if "База клиентов" not in str(f)] or files
        f = sorted(pref)[len(pref) // 2]  # средний по алфавиту — обычно «обычный» месяц
        print(f"### {cd.name}  | файлов: {len(files)}")
        print(f"    пример: {f.relative_to(cd)}")
        try:
            xl = pd.ExcelFile(f)
            for sh in xl.sheet_names[:5]:
                df = xl.parse(sh, header=None, nrows=6, dtype=str).fillna("")
                print(f"    [{sh}] {header_guess(df)}")
        except Exception as e:
            print(f"    ошибка чтения: {e}")
        print()


if __name__ == "__main__":
    main()
