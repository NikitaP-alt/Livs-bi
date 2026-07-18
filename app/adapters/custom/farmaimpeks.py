"""Фармаимпекс: в одном файле 2 листа — продажи («февраль»/месяц) и «ост» (остатки).
Используем авто-движок (он читает оба листа и сам определяет факты), но под каноническим
именем клиента «Фармаимпекс»."""
from .. import auto

CLIENT = "Фармаимпекс"


def adapt(file_path, period_override=None):
    return auto.adapt(file_path, period_override, CLIENT)
