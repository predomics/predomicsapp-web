#!/usr/bin/env bash
# PredomicsApp — Backup Script
#
# Creates timestamped PostgreSQL dumps and data volume archives.
# Run manually or add to cron:  0 2 * * * /path/to/backup.sh
#
# Usage:
#   ./scripts/backup.sh                    # default: 7-day retention
#   BACKUP_RETENTION_DAYS=30 ./scripts/backup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_DIR}/backups"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "=== PredomicsApp Backup — $TIMESTAMP ==="

# --------------------------------------------------------------------------
# 1. PostgreSQL dump (custom format for efficient restore)
# --------------------------------------------------------------------------
echo "[1/2] Dumping PostgreSQL database..."
DB_FILE="${BACKUP_DIR}/db_${TIMESTAMP}.dump"
docker exec predomics-db pg_dump -U predomics -Fc predomics > "$DB_FILE" 2>/dev/null

if [ -s "$DB_FILE" ]; then
    echo "      Database dump: $(du -h "$DB_FILE" | cut -f1)"
else
    echo "      WARNING: Database dump is empty or failed"
    rm -f "$DB_FILE"
fi

# --------------------------------------------------------------------------
# 2. Data volume archive (uploads, projects, datasets)
# --------------------------------------------------------------------------
echo "[2/2] Archiving data volume..."
DATA_FILE="${BACKUP_DIR}/data_${TIMESTAMP}.tar.gz"
docker run --rm \
    -v predomics_app-data:/data:ro \
    -v "${BACKUP_DIR}":/backup \
    alpine tar czf "/backup/data_${TIMESTAMP}.tar.gz" -C /data . 2>/dev/null

if [ -s "$DATA_FILE" ]; then
    echo "      Data archive: $(du -h "$DATA_FILE" | cut -f1)"
else
    echo "      WARNING: Data archive is empty or failed"
fi

# --------------------------------------------------------------------------
# 3. Retention cleanup
# --------------------------------------------------------------------------
echo "Cleaning up backups older than ${RETENTION_DAYS} days..."
DELETED=0
while IFS= read -r -d '' f; do
    rm -f "$f"
    DELETED=$((DELETED + 1))
done < <(find "$BACKUP_DIR" \( -name "db_*.dump" -o -name "data_*.tar.gz" \) -mtime +"$RETENTION_DAYS" -print0 2>/dev/null)
echo "      Removed $DELETED old backup(s)"

echo ""
echo "=== Backup complete ==="
echo "Location: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"/db_"${TIMESTAMP}"* "$BACKUP_DIR"/data_"${TIMESTAMP}"* 2>/dev/null || true
