-- Сводка по каналам продаж: сеть/группа + канал + Sell-In (1С) + Sell-Out.
-- Доля клиента в Sell-In (ответ на «долю клиента», зад.5) считается в карточке.
CREATE OR REPLACE VIEW marts.v_channel_summary AS
WITH ch AS (
    SELECT group_name g, MIN(channel_type) channel
    FROM core.dim_client WHERE group_name IS NOT NULL GROUP BY 1
), si AS (
    SELECT dc.group_name g, SUM(f.rub) rub, SUM(f.qty) qty
    FROM core.fact_sellin f JOIN core.dim_client dc ON dc.client_id = f.client_id GROUP BY 1
), so AS (
    SELECT dc.group_name g, SUM(f.qty) qty
    FROM core.fact_sellout f JOIN core.dim_client dc ON dc.client_id = f.client_id GROUP BY 1
), grp AS (
    SELECT g FROM si UNION SELECT g FROM so
)
SELECT
    grp.g                          AS "Сеть/группа",
    COALESCE(ch.channel, '—')      AS "Канал",
    si.rub                         AS "Sell-In, руб",
    si.qty                         AS "Sell-In, шт",
    so.qty                         AS "Sell-Out, шт"
FROM grp
LEFT JOIN ch ON ch.g = grp.g
LEFT JOIN si ON si.g = grp.g
LEFT JOIN so ON so.g = grp.g;
