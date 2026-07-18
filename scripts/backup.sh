#!/usr/bin/env bash
# Бэкап БД livs_bi в backups/*.sql.gz, хранит последние 14.
# Запуск: bash scripts/backup.sh   (или из cron)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .env ]; then set -a; . ./.env; set +a; fi
PGUSER="${POSTGRES_USER:-livs}"
PGDB="${POSTGRES_DB:-livs_bi}"

mkdir -p backups
ts="$(date +%Y%m%d_%H%M%S)"
out="backups/livs_bi_${ts}.sql.gz"

docker compose exec -T db pg_dump -U "$PGUSER" "$PGDB" | gzip > "$out"

# держим только последние 14 копий
ls -1t backups/*.sql.gz 2>/dev/null | tail -n +15 | xargs -r rm -f

echo "backup done: $out"
