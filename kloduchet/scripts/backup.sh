#!/usr/bin/env bash
# Резервное копирование «КлодУчет» (tech_spec.md, раздел 16).
# Делает дамп PostgreSQL, копию каталога оригиналов загруженных файлов
# и файл с версией приложения и датой копии.
#
# Использование (из каталога kloduchet/, при запущенном `docker compose up`):
#   ./scripts/backup.sh [каталог_для_бэкапов]
#
# По умолчанию бэкапы складываются в ./backups/<дата>_<время>/

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${1:-$ROOT_DIR/backups}"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
TARGET_DIR="$BACKUP_ROOT/$STAMP"

mkdir -p "$TARGET_DIR"

echo "Делаю дамп PostgreSQL..."
docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-kloduchet}" "${POSTGRES_DB:-kloduchet}" \
  > "$TARGET_DIR/database.sql"

echo "Копирую оригиналы загруженных файлов..."
cp -r "$ROOT_DIR/data" "$TARGET_DIR/data"

GIT_COMMIT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
cat > "$TARGET_DIR/MANIFEST.txt" <<EOF
КлодУчет — резервная копия
Дата: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
Версия (git commit): $GIT_COMMIT
Содержимое:
  - database.sql — дамп PostgreSQL (pg_dump)
  - data/ — оригиналы загруженных файлов
EOF

echo "Готово: $TARGET_DIR"
