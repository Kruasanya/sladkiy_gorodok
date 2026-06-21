#!/usr/bin/env bash
# Восстановление «КлодУчет» из резервной копии, созданной backup.sh
# (tech_spec.md, раздел 16).
#
# Использование (из каталога kloduchet/, при запущенном `docker compose up`):
#   ./scripts/restore.sh backups/2026-06-21_12-00-00
#
# ВНИМАНИЕ: перезаписывает текущую базу данных и каталог data/. Перед
# восстановлением в реальной эксплуатации сначала сделайте свежий backup.sh.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${1:?Укажите каталог резервной копии, например backups/2026-06-21_12-00-00}"

if [ ! -f "$SOURCE_DIR/database.sql" ]; then
  echo "Не найден $SOURCE_DIR/database.sql" >&2
  exit 1
fi

echo "Восстанавливаю PostgreSQL из $SOURCE_DIR/database.sql..."
cat "$SOURCE_DIR/database.sql" | docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T postgres \
  psql -U "${POSTGRES_USER:-kloduchet}" "${POSTGRES_DB:-kloduchet}"

echo "Восстанавливаю каталог data/..."
rm -rf "$ROOT_DIR/data"
cp -r "$SOURCE_DIR/data" "$ROOT_DIR/data"

echo "Готово. Проверьте приложение перед началом реальной эксплуатации (раздел 16 tech_spec.md)."
