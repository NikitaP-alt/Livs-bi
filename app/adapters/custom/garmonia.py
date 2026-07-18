"""Гармония Здоровья (Красноярск): Продажи_MM.YY (Лист1, «СумКол») и Остатки_MM.YY («СумКолОстКП»).
Авто-движок (знает «СумКол»/«СумКолОстКП») под каноническим именем. Сводные «Отчеты Ливс» и
диапазонные файлы пропускаем в registry (skip_files), чтобы не задвоить."""
from .. import auto

CLIENT = "Гармония Здоровья"


def adapt(file_path, period_override=None):
    return auto.adapt(file_path, period_override, CLIENT)
