# Деплой на боевой сервер (РФ)

Сервер: Ubuntu 22.04 LTS, РФ/Москва, ~8 ГБ RAM, 80 ГБ диск. Домен указывает на сервер.
Стек тот же, что локально, + Caddy (HTTPS) и автозапуск.

## 0. DNS
Создай A-запись: `bi.твойдомен.ru` → IP сервера. Подожди, пока резолвится.

## 1. Базовая подготовка сервера (по SSH, под root/sudo)
```bash
apt update && apt -y upgrade
# Docker (официальный скрипт)
curl -fsSL https://get.docker.com | sh
# firewall: оставляем только SSH + HTTP + HTTPS
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
```
> На 8 ГБ swap не обязателен, но не помешает:
> `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile && echo '/swapfile none swap sw 0 0' >> /etc/fstab`

## 2. Доставить проект ИЗ СНАПШОТА (сохраняет данные + дашборды)
Снапшот `livs-bi_snapshot_YYYY-MM-DD.tar.gz` уже содержит код + дамп БД (`backup/livs_bi.dump`)
+ H2-файл Metabase со всеми дашбордами (`metabase-data/`).
```bash
mkdir -p /opt && cd /opt
# scp с локальной машины (из Git Bash):  scp d:/ToLivs/snapshots/livs-bi_snapshot_*.tar.gz root@SERVER:/opt/
tar -xzf livs-bi_snapshot_*.tar.gz          # -> /opt/livs-bi
cd /opt/livs-bi
ls metabase-data/metabase.db.mv.db backup/livs_bi.dump   # проверка: оба на месте
```

## 3. Настроить .env (боевой)
```bash
# .env уже в снапшоте. Сгенерировать стойкий пароль БД:
NEWPW=$(openssl rand -hex 24)
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEWPW/" .env
# прописать домен и почту:
sed -i "s/^DOMAIN=.*/DOMAIN=bi.твойдомен.ru/" .env
sed -i "s/^ACME_EMAIL=.*/ACME_EMAIL=admin@твойдомен.ru/" .env
echo "новый пароль БД: $NEWPW"   # понадобится в шаге 5
```

## 4. Запуск (с продакшен-оверлеем)
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps          # дождись healthy у db
```
Caddy сам получит HTTPS-сертификат для домена (может занять минуту).
Metabase остаётся на H2 (оверлей НЕ переключает на Postgres) → дашборды из снапшота уже на месте.

## 5. Восстановить данные хранилища + починить подключение Metabase
```bash
# 5.1 залить дамп поверх чистой инициализации (полное состояние = как локально):
docker compose exec -T db pg_restore --clean --if-exists --no-owner -U livs -d livs_bi < backup/livs_bi.dump
# (варнинги про несуществующие объекты при --clean — норма)

# 5.2 Metabase (H2) хранит подключение к БД со СТАРЫМ паролем. Обновить на новый — из шага 3.
#     Проще всего в UI: https://bi.твойдомен.ru → Admin → Databases → livs_bi → пароль = $NEWPW → Save.
#     (Логин админа/юзеров — те же, что локально: admin = email; view-only = viewer@livs.local.)
```
Проверь: открой дашборд — данные грузятся, все 15 дашбордов на месте, русский интерфейс.

## 6. Доступ людям
Settings → People → пригласить Наталью/Ольгу/КАМ (роль «только просмотр»).

## 7. Бэкапы
```bash
bash scripts/backup.sh                      # разовый
# ежедневно в 3:30 ночи:
( crontab -l 2>/dev/null; echo "30 3 * * * cd /opt/livs-bi && bash scripts/backup.sh" ) | crontab -
```
Бэкапы лягут в `/opt/livs-bi/backups/` (хранятся последние 14). Периодически копируй их
в отдельное место (другой диск/хранилище).

## 8. Обновления / рестарт
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull   # обновить образы
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d  # применить
docker compose logs -f --tail=100 metabase                            # смотреть логи
```

## Безопасность (коротко)
- Postgres наружу НЕ открыт (только внутри Docker-сети + localhost). 5432 в firewall не открываем.
- Наружу торчит только Caddy (80/443). Metabase — за ним, по HTTPS, с логином.
- Пароль БД — сгенерированный, не `change_me`.
- ПДн остаются в РФ (152-ФЗ) — сервер в Москве.
