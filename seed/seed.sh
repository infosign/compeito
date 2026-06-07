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

cd "$REPO_ROOT"

# Force English locale so message parsing is independent of host LANG.
export LANG=C

# Decide how to invoke the CLI: native (`uv run`) vs Docker (`docker compose exec app uv run`).
# If the `app` service is up in docker compose, use Docker. Otherwise assume native.
if command -v docker >/dev/null 2>&1 && docker compose ps -q app 2>/dev/null | grep -q .; then
    RUN_CMD=(docker compose exec -T -e LANG=C app uv run)
    # Repo root is mounted at /app inside the container.
    CSV_PATH="${CSV_FILE#$REPO_ROOT/}"
    MODE=docker
else
    RUN_CMD=(uv run)
    CSV_PATH="$CSV_FILE"
    MODE=native
fi
echo "==> Mode: $MODE"

# Run migration
echo "==> Running database migration..."
"${RUN_CMD[@]}" alembic upgrade head

# Create tenant
echo "==> Creating tenant: $TENANT_NAME"
OUTPUT=$("${RUN_CMD[@]}" python cli.py tenant create --name "$TENANT_NAME")
OUTPUT="${OUTPUT//$'\r'/}"
echo "$OUTPUT"

# Extract UUID from "Created tenant: {uuid} (...)"
TENANT_UUID=$(echo "$OUTPUT" | grep -oE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" | head -1)

if [ -z "$TENANT_UUID" ]; then
    echo "Error: Failed to extract tenant UUID" >&2
    exit 1
fi

# Import CSV
echo "==> Importing CSV: $CSV_PATH"
IMPORT_OUTPUT=$("${RUN_CMD[@]}" python cli.py import csv --tenant "$TENANT_UUID" --file "$CSV_PATH")
IMPORT_OUTPUT="${IMPORT_OUTPUT//$'\r'/}"
echo "$IMPORT_OUTPUT"

# Extract document UUID from import output "Imported into '...' (uuid)"
DOC_UUID=$(echo "$IMPORT_OUTPUT" | grep -oE "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}" | head -1)

# Import rubric CSV if it exists (same base name + "r" suffix)
RUBRIC_FILE="${CSV_FILE%.csv}r.csv"
if [ -f "$RUBRIC_FILE" ] && [ -n "$DOC_UUID" ]; then
    if [ "$MODE" = "docker" ]; then
        RUBRIC_PATH="${RUBRIC_FILE#$REPO_ROOT/}"
    else
        RUBRIC_PATH="$RUBRIC_FILE"
    fi
    echo "==> Importing rubric CSV: $RUBRIC_PATH"
    "${RUN_CMD[@]}" python cli.py import rubric --tenant "$TENANT_UUID" --doc "$DOC_UUID" --file "$RUBRIC_PATH"
fi

echo "==> Done! Tenant: $TENANT_UUID ($TENANT_NAME)"
