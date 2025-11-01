#!/bin/bash

# Database backup script
# Creates timestamped pg_dump backup with compression

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-minimee}"
DB_USER="${DB_USER:-minimee}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/minimee_backup_${TIMESTAMP}.sql.gz"

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

echo "📦 Creating database backup..."
echo "Database: ${DB_NAME}"
echo "Output: ${BACKUP_FILE}"

# Perform backup with compression
PGPASSWORD="${DB_PASSWORD:-minimee}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --clean \
    --if-exists \
    --format=custom \
    -f "${BACKUP_FILE%.gz}" 2>/dev/null || \
PGPASSWORD="${DB_PASSWORD:-minimee}" pg_dump \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    --clean \
    -f "${BACKUP_FILE%.gz}"

# Compress backup
if [ -f "${BACKUP_FILE%.gz}" ]; then
    gzip "${BACKUP_FILE%.gz}"
    echo "✅ Backup created: ${BACKUP_FILE}"
    
    # Show backup size
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "   Size: ${SIZE}"
else
    echo "❌ Backup failed"
    exit 1
fi

# Optional: Keep only last N backups (default: 10)
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"
if [ "${KEEP_BACKUPS}" -gt 0 ]; then
    ls -t "${BACKUP_DIR}"/minimee_backup_*.sql.gz 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | xargs -r rm
    echo "   Kept last ${KEEP_BACKUPS} backups"
fi

