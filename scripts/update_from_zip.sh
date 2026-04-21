#!/bin/sh
set -eu

usage() {
  echo "Usage: $0 /path/to/update.zip [--no-migrate]"
  echo "Run from project root or keep this script in scripts/ and run it directly."
}

ZIP_PATH="${1:-}"
RUN_MIGRATIONS="${2:-}"
AUTO_MIGRATE="1"

if [ "$RUN_MIGRATIONS" = "--no-migrate" ]; then
  AUTO_MIGRATE="0"
fi

if [ -z "$ZIP_PATH" ]; then
  usage
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if [ ! -f "$ROOT_DIR/docker-compose.yml" ]; then
  echo "docker-compose.yml not found in $ROOT_DIR"
  exit 1
fi

if [ ! -f "$ZIP_PATH" ]; then
  echo "Zip not found: $ZIP_PATH"
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip is required."
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required."
  exit 1
fi

BACKUP_DIR="$ROOT_DIR/backups"
mkdir -p "$BACKUP_DIR"
STAMP=$(date +%Y%m%d_%H%M%S)

DATA_DIRS="instance REPORTS"
BACKUP_ITEMS=""
for d in $DATA_DIRS; do
  if [ -e "$ROOT_DIR/$d" ]; then
    BACKUP_ITEMS="$BACKUP_ITEMS $d"
  fi
done

if [ -n "$BACKUP_ITEMS" ]; then
  tar -czf "$BACKUP_DIR/data_${STAMP}.tgz" -C "$ROOT_DIR" $BACKUP_ITEMS
  echo "Backup created: $BACKUP_DIR/data_${STAMP}.tgz"
else
  echo "No data directories found to back up."
fi

TMP_DIR="$ROOT_DIR/_tmp_update_${STAMP}"
mkdir -p "$TMP_DIR"
unzip -q "$ZIP_PATH" -d "$TMP_DIR"

APP_PATH=$(find "$TMP_DIR" -maxdepth 3 -type f -name app.py -print -quit 2>/dev/null || true)
if [ -z "$APP_PATH" ]; then
  echo "app.py not found in the zip."
  rm -rf "$TMP_DIR"
  exit 1
fi

SRC_DIR=$(dirname "$APP_PATH")

rsync -a --delete \
  --exclude '/instance' \
  --exclude '/REPORTS' \
  --exclude '/backups' \
  --exclude '/.env' \
  --exclude '/.venv' \
  --exclude '/__pycache__' \
  --exclude '*.log' \
  --exclude '*.log.*' \
  "$SRC_DIR"/ "$ROOT_DIR"/

rm -rf "$TMP_DIR"

if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "docker compose not found."
  exit 1
fi

$COMPOSE_CMD up -d --build

if [ "$AUTO_MIGRATE" = "1" ]; then
  SERVICE_NAME="${SERVICE_NAME:-staff_planner}"
  if ls "$ROOT_DIR"/migration_*.py >/dev/null 2>&1; then
    for f in "$ROOT_DIR"/migration_*.py; do
      [ -f "$f" ] || break
      echo "Running migration: $(basename "$f")"
      $COMPOSE_CMD exec -T "$SERVICE_NAME" python "$(basename "$f")"
    done
  fi
else
  if ls "$ROOT_DIR"/migration_*.py >/dev/null 2>&1; then
    echo "Migration files detected. Skipped due to --no-migrate."
  fi
fi

echo "Update complete."
