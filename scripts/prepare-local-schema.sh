#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CLI="${SUPABASE_CLI:-supabase}"
REF="${SUPABASE_PROJECT_REF:-dmttevcncsxzbamazmmq}"
BASELINE="$ROOT/supabase/migrations/20261114000000_remote_schema.sql"

command -v "$CLI" >/dev/null 2>&1 || { echo "Supabase CLI is required." >&2; exit 1; }
[[ ! -e "$BASELINE" ]] || { echo "Refusing to overwrite existing baseline: $BASELINE" >&2; exit 1; }

echo "This links the CLI and exports schema DDL only. It does not insert data or run remote migrations."
echo "The baseline contains no customer/order rows and is ignored by Git."
read -r -p "Export schema-only baseline from '$REF'? Type EXPORT-SCHEMA: " CONFIRM
[[ "$CONFIRM" == "EXPORT-SCHEMA" ]] || { echo "Cancelled."; exit 1; }

"$CLI" link --project-ref "$REF"
"$CLI" db dump --linked --schema public,private,extensions --file "$BASELINE"
[[ -s "$BASELINE" ]] || { echo "Schema dump was empty." >&2; exit 1; }

echo "Created local schema-only baseline: $BASELINE"
echo "Next: scripts/run-prelaunch-tests.sh"
echo "Never run 'supabase db push' or 'supabase db reset --linked' for this workflow."
