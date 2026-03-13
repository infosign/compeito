#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TENANT_NAME="${1:-池之端大学}"
CSV_FILE="${2:-${SCRIPT_DIR}/001.csv}"

if [ ! -f "$CSV_FILE" ]; then
    echo "Error: CSV file not found: $CSV_FILE" >&2
    exit 1
fi

# Path inside container (repo root is mounted at /app)
CSV_CONTAINER_PATH="${CSV_FILE#$REPO_ROOT/}"

cd "$REPO_ROOT"

# Run migration
echo "==> Running database migration..."
docker compose exec -T app uv run alembic upgrade head

# Create tenant
echo "==> Creating tenant: $TENANT_NAME"
OUTPUT=$(docker compose exec -T app uv run python cli.py tenant create --name "$TENANT_NAME")
OUTPUT="${OUTPUT//$'\r'/}"
echo "$OUTPUT"

# Extract UUID from "Created tenant: {uuid} (...)"
TENANT_UUID="${OUTPUT#*Created tenant: }"
TENANT_UUID="${TENANT_UUID%% *}"

if [ -z "$TENANT_UUID" ]; then
    echo "Error: Failed to extract tenant UUID" >&2
    exit 1
fi

# Import CSV
echo "==> Importing CSV: $CSV_CONTAINER_PATH"
IMPORT_OUTPUT=$(docker compose exec -T app uv run python cli.py import csv --tenant "$TENANT_UUID" --file "$CSV_CONTAINER_PATH")
IMPORT_OUTPUT="${IMPORT_OUTPUT//$'\r'/}"
echo "$IMPORT_OUTPUT"

# Extract document UUID from import output "Imported into '...' (uuid)"
DOC_UUID=$(echo "$IMPORT_OUTPUT" | sed -n "s/.*(\([0-9a-f-]*\)).*/\1/p" | head -1)

# Import rubric CSV if it exists (same base name + "r" suffix)
RUBRIC_FILE="${CSV_FILE%.csv}r.csv"
if [ -f "$RUBRIC_FILE" ] && [ -n "$DOC_UUID" ]; then
    RUBRIC_CONTAINER_PATH="${RUBRIC_FILE#$REPO_ROOT/}"
    echo "==> Importing rubric CSV: $RUBRIC_CONTAINER_PATH"
    docker compose exec -T app uv run python cli.py import csv-rubric --tenant "$TENANT_UUID" --doc "$DOC_UUID" --file "$RUBRIC_CONTAINER_PATH"
fi

echo "==> Done! Tenant: $TENANT_UUID ($TENANT_NAME)"
