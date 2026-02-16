#!/usr/bin/env bash
# PredomicsApp — Restore Script
#
# Restores a PostgreSQL dump and/or data volume from a backup timestamp.
#
# Usage:
#   ./scripts/restore.sh 20260215_020000          # restore both DB + data
#   ./scripts/restore.sh 20260215_020000 --db      # restore database only
#   ./scripts/restore.sh 20260215_020000 --data    # restore data volume only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"

# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------
if [ $# -lt 1 ]; then
    echo "Usage: $0 <TIMESTAMP> [--db|--data]"
    echo ""
    echo "Available backups:"
    ls -1 "$BACKUP_DIR"/db_*.dump 2>/dev/null | sed 's/.*db_//;s/\.dump//' | sort -r || echo "  (none)"
    exit 1
fi

TIMESTAMP="$1"
MODE="${2:---all}"

DB_FILE="${BACKUP_DIR}/db_${TIMESTAMP}.dump"
DATA_FILE="${BACKUP_DIR}/data_${TIMESTAMP}.tar.gz"

# --------------------------------------------------------------------------
# Validate backup files exist
# --------------------------------------------------------------------------
if [ "$MODE" = "--all" ] || [ "$MODE" = "--db" ]; then
    if [ ! -f "$DB_FILE" ]; then
        echo "ERROR: Database backup not found: $DB_FILE"
        exit 1
    fi
fi

if [ "$MODE" = "--all" ] || [ "$MODE" = "--data" ]; then
    if [ ! -f "$DATA_FILE" ]; then
        echo "ERROR: Data backup not found: $DATA_FILE"
        exit 1
    fi
fi

echo "=== PredomicsApp Restore — $TIMESTAMP ==="
echo ""
echo "WARNING: This will overwrite current data. The app will be stopped during restore."
read -rp "Continue? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

# --------------------------------------------------------------------------
# Stop the application
# --------------------------------------------------------------------------
echo ""
echo "Stopping application..."
cd "$PROJECT_DIR"
docker compose stop app

# --------------------------------------------------------------------------
# Restore database
# --------------------------------------------------------------------------
if [ "$MODE" = "--all" ] || [ "$MODE" = "--db" ]; then
    echo ""
    echo "Restoring database from $DB_FILE ..."
    docker exec -i predomics-db pg_restore \
        -U predomics -d predomics --clean --if-exists --no-owner \
        < "$DB_FILE"
    echo "Database restored."
fi

# --------------------------------------------------------------------------
# Restore data volume
# --------------------------------------------------------------------------
if [ "$MODE" = "--all" ] || [ "$MODE" = "--data" ]; then
    echo ""
    echo "Restoring data volume from $DATA_FILE ..."
    docker run --rm \
        -v predomics_app-data:/data \
        -v "${BACKUP_DIR}":/backup:ro \
        alpine sh -c "rm -rf /data/* && tar xzf /backup/data_${TIMESTAMP}.tar.gz -C /data"
    echo "Data volume restored."
fi

# --------------------------------------------------------------------------
# Restart the application
# --------------------------------------------------------------------------
echo ""
echo "Restarting application..."
docker compose start app

echo ""
echo "=== Restore complete ==="
