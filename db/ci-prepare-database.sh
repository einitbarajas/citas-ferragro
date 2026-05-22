#!/usr/bin/env bash
# Prepara PostgreSQL para pytest con BD en CI (GitHub Actions o local).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INIT_DIR="$ROOT/db/init"
CRUD_DIR="$ROOT/db/database-crud"

if [[ -z "${PGHOST:-}" ]]; then
  echo "PGHOST no definido; usa variables estándar de psql (PGHOST, PGUSER, PGPASSWORD, PGDATABASE)."
  exit 1
fi

echo "=== Ferragro CI: init scripts ==="
for f in $(ls "$INIT_DIR"/*.sql 2>/dev/null | sort); do
  echo "Applying $(basename "$f")"
  psql -v ON_ERROR_STOP=1 -f "$f"
done

echo "=== Ferragro CI: database-crud (PL/pgSQL) ==="
while IFS= read -r -d '' file; do
  echo "Applying ${file#$ROOT/}"
  psql -v ON_ERROR_STOP=1 -f "$file"
done < <(find "$CRUD_DIR" -name '*.sql' -type f | sort -z)

echo "=== Ferragro CI: fixtures mínimos para pytest ==="
psql -v ON_ERROR_STOP=1 -f "$ROOT/db/ci/fixtures_for_tests.sql"

echo "=== Base lista para pruebas con BD ==="
