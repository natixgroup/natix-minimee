#!/bin/bash
# Start script with syntax validation
# This ensures the server doesn't start with syntax errors

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔍 Validating Python syntax..."
python3 "$SCRIPT_DIR/validate_syntax.py"

if [ $? -ne 0 ]; then
    echo "❌ Syntax validation failed. Server will not start."
    exit 1
fi

echo "✅ Syntax validation passed. Starting server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

