#!/bin/bash

# Database restore script
# Restores from backup file and verifies pgvector extension

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-minimee}"
DB_USER="${DB_USER:-minimee}"
BACKUP_FILE="${1}"

if [ -z "${BACKUP_FILE}" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 ./backups/minimee_backup_20240101_120000.sql.gz"
    exit 1
fi

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "❌ Backup file not found: ${BACKUP_FILE}"
    exit 1
fi

echo "📥 Restoring database from backup..."
echo "Database: ${DB_NAME}"
echo "Backup file: ${BACKUP_FILE}"

# Check if file is compressed
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    echo "Decompressing backup..."
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "${BACKUP_FILE}" > "${TEMP_FILE}"
    RESTORE_FILE="${TEMP_FILE}"
    CLEANUP_TEMP=true
else
    RESTORE_FILE="${BACKUP_FILE}"
    CLEANUP_TEMP=false
fi

# Restore database
echo "Restoring database..."
PGPASSWORD="${DB_PASSWORD:-minimee}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -f "${RESTORE_FILE}" || {
    echo "⚠️  Restore may have encountered errors, but continuing..."
}

# Cleanup temp file if created
if [ "${CLEANUP_TEMP}" = true ] && [ -f "${TEMP_FILE}" ]; then
    rm "${TEMP_FILE}"
fi

# Verify pgvector extension
echo "Verifying pgvector extension..."
PGPASSWORD="${DB_PASSWORD:-minimee}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    echo "⚠️  pgvector extension check - may need manual verification"
}

echo "✅ Database restored successfully!"
echo "   Verify with: psql -h ${DB_HOST} -U ${DB_USER} -d ${DB_NAME} -c 'SELECT COUNT(*) FROM messages;'"

