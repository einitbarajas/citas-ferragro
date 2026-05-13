#!/usr/bin/env bash
set -euo pipefail

DB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATABASE_URL="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "Define DATABASE_URL (URI postgresql://...) antes de ejecutar este script." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "Instala el cliente psql (PostgreSQL) para aplicar los scripts SQL." >&2
  exit 1
fi

run_sql() {
  local label="$1"
  local file="$2"
  echo ""
  echo "==> $label"
  psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$file"
}

INIT_FILES=(
  "init/001_schema.sql"
  "init/002_audit_triggers.sql"
  "init/003_historial_id_actor_drop_fk.sql"
  "init/004_franjas_citas.sql"
  "init/005_profile_photo.sql"
  "init/006_admin_events.sql"
  "init/007_nit_10_digits.sql"
  "init/009_franjas_por_fecha.sql"
  "init/010_drop_dias_permitidos_cita.sql"
  "init/011_auth_sessions_login_audit.sql"
  "init/012_db_roles_template.sql"
)

echo "=== Ferragro: despliegue de base de datos (init + CRUD) ==="

for rel in "${INIT_FILES[@]}"; do
  run_sql "$rel" "$DB_DIR/$rel"
done

while IFS= read -r crud_file; do
  run_sql "${crud_file#"$DB_DIR/"}" "$crud_file"
done < <(find "$DB_DIR/database-crud" -type f -name '*.sql' | sort)

if [[ "${1:-}" == "--seed" ]]; then
  run_sql "seeds/003_seed_data.sql" "$DB_DIR/seeds/003_seed_data.sql"
fi

echo ""
echo "=== Completado sin errores. ==="
