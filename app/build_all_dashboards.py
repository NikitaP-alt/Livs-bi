"""Пересобрать все скриптовые дашборды одной командой (идемпотентно).

Полезно после восстановления БД/переноса, если нужно перегенерировать аналитические дашборды
(id 5,6,36,37,38) и починить фильтры основных (id 2,3). Дашборды 2/3/4 собраны вручную —
их карточки скрипты не создают, но fix_main_filters пере-привязывает у 2/3 фильтры.

Запуск: docker compose exec -T app python -m app.build_all_dashboards
"""
from . import (build_channels_dashboard, build_coverage_dashboard, build_dynamics_dashboard,
               build_profit_dashboard, build_recon_dashboard, fix_main_filters)

STEPS = [
    ("Сверка Sell-In/Sell-Out", build_recon_dashboard.main),
    ("Доходность", build_profit_dashboard.main),
    ("Динамика и прирост", build_dynamics_dashboard.main),
    ("Клиенты и каналы", build_channels_dashboard.main),
    ("Остатки: покрытие", build_coverage_dashboard.main),
    ("Фильтры основных дашбордов (id 2/3)", fix_main_filters.main),
]


def main():
    for title, fn in STEPS:
        print(f"\n===== {title} =====")
        fn()
    print("\nВсе дашборды пересобраны.")


if __name__ == "__main__":
    main()
