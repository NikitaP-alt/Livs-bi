"""Социальная аптека: продажи и остатки — отдельными файлами, + варианты форматов.
Авто-движок под каноническим именем (берёт продажи -> sellout, остатки/ОСГ -> stock)."""
from .. import auto

CLIENT = "Социальная аптека"


def adapt(file_path, period_override=None):
    return auto.adapt(file_path, period_override, CLIENT)
