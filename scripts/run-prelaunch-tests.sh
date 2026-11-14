#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
CLI="${SUPABASE_CLI:-supabase}"
DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"

command -v "$CLI" >/dev/null 2>&1 || { echo "Supabase CLI is not installed." >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required." >&2; exit 1; }
command -v psql >/dev/null 2>&1 || { echo "psql is required." >&2; exit 1; }
[[ -s "supabase/migrations/20261114000000_remote_schema.sql" ]] || {
  echo "Missing schema baseline. Run scripts/prepare-local-schema.sh first." >&2; exit 1;
}
case "$DATABASE_URL" in
  *dmttevcncsxzbamazmmq*) echo "SAFETY STOP: production database URL is blocked." >&2; exit 1 ;;
esac
[[ "$DATABASE_URL" == *127.0.0.1* || "$DATABASE_URL" == *localhost* ]] || {
  echo "SAFETY STOP: LOCAL_DATABASE_URL must point to localhost." >&2; exit 1;
}

echo "1/4 - Start local Supabase"
"$CLI" start

echo "2/4 - Rebuild the LOCAL database only"
"$CLI" db reset --local

echo "3/4 - Validate storefront and backend source"
node tests/validate-store.mjs

echo "4/4 - Run transactional PostgreSQL integration tests"
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/tests/prelaunch-hardening.sql

echo "Local integration tests completed. The hosted database was not modified."
