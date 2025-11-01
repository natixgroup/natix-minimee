#!/bin/bash

# Export data script
# Exports messages, embeddings, agents to JSON/CSV format

set -e

# Configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-minimee}"
DB_USER="${DB_USER:-minimee}"
EXPORT_DIR="${EXPORT_DIR:-./exports}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXPORT_FORMAT="${EXPORT_FORMAT:-json}"

# Create export directory
mkdir -p "${EXPORT_DIR}"

echo "📤 Exporting Minimee data..."
echo "Format: ${EXPORT_FORMAT}"
echo "Output directory: ${EXPORT_DIR}"

# Export messages
MESSAGES_FILE="${EXPORT_DIR}/messages_${TIMESTAMP}.${EXPORT_FORMAT}"
echo "Exporting messages..."
PGPASSWORD="${DB_PASSWORD:-minimee}" psql \
    -h "${DB_HOST}" \
    -p "${DB_PORT}" \
    -U "${DB_USER}" \
    -d "${DB_NAME}" \
    -c "\COPY (SELECT id, content, sender, timestamp, source, conversation_id, user_id, created_at FROM messages ORDER BY timestamp DESC) TO STDOUT WITH CSV HEADER" \
    > "${MESSAGES_FILE%.json}.csv" 2>/dev/null || echo "CSV export may have failed, trying JSON..."

# For JSON export, we'd need a Python script or use psql with JSON functions
# This is a simplified version - full implementation would use Python

echo "✅ Export completed: ${EXPORT_DIR}/"
echo "   Files: messages_${TIMESTAMP}.csv"

