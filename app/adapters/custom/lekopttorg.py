"""ЛекОптТорг (СПБ): много форматов по годам (Препарат/шт, «Анализ продаж», SKU ID).
Авто-движок под каноническим именем. Акции пропускаем в registry (skip_files)."""
from .. import auto

CLIENT = "ЛекОптТорг"


def adapt(file_path, period_override=None):
    return auto.adapt(file_path, period_override, CLIENT)
