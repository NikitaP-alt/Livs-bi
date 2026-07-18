-- Отдельная БД для настроек самого Metabase (надёжнее, чем встроенная H2 на проде).
-- Выполняется при первой инициализации Postgres (до 01_schema.sql).
CREATE DATABASE metabaseapp;
