#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
command -v psql >/dev/null 2>&1 || { echo "psql is required." >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "curl is required to remove the local Storage fixture." >&2; exit 1; }
[[ "${ELORY_LOAD_TEST_CLEANUP:-}" == "YES" ]] || { echo "Set ELORY_LOAD_TEST_CLEANUP=YES to remove synthetic test rows." >&2; exit 1; }
case "$DATABASE_URL" in *dmttevcncsxzbamazmmq*) echo "SAFETY STOP: production cleanup is blocked." >&2; exit 1 ;; esac
[[ "$DATABASE_URL" == *127.0.0.1* || "$DATABASE_URL" == *localhost* ]] || { echo "LOCAL_DATABASE_URL must point to localhost." >&2; exit 1; }

if [[ -f "supabase/.env.test" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "supabase/.env.test"
  set +a
fi
SUPABASE_URL="${SUPABASE_URL:-http://127.0.0.1:54321}"
SERVICE_ROLE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-${ELORY_SERVICE_ROLE_KEY:-}}"
[[ -n "$SERVICE_ROLE_KEY" ]] || { echo "Local SUPABASE_SERVICE_ROLE_KEY is required to clean the Storage fixture." >&2; exit 1; }
case "$SUPABASE_URL" in
  http://127.0.0.1:*|http://localhost:*) ;;
  *) echo "SAFETY STOP: Storage cleanup URL must point to localhost." >&2; exit 1 ;;
esac
[[ "$SUPABASE_URL" != *dmttevcncsxzbamazmmq* ]] || { echo "SAFETY STOP: production Storage cleanup is blocked." >&2; exit 1; }

# Remove ordinary rows first. Order deletion fires the inventory-restore trigger.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/test/cleanup-10000.sql

# Supabase protects storage.objects from direct SQL writes. Use the Storage API.
headers=(-H "apikey: $SERVICE_ROLE_KEY" -H "Authorization: Bearer $SERVICE_ROLE_KEY")
response_file="$(mktemp)"
trap 'rm -f "$response_file"' EXIT

status="$(curl --silent --show-error --output "$response_file" --write-out '%{http_code}' \
  -X DELETE "$SUPABASE_URL/storage/v1/object/elory-load-test/product.png" "${headers[@]}")"
case "$status" in
  200|204|404) ;;
  *) echo "Local Storage object deletion failed (HTTP $status): $(cat "$response_file")" >&2; exit 1 ;;
esac

status="$(curl --silent --show-error --output "$response_file" --write-out '%{http_code}' \
  -X DELETE "$SUPABASE_URL/storage/v1/bucket/elory-load-test" "${headers[@]}")"
case "$status" in
  200|204|404) ;;
  *) echo "Local Storage bucket deletion failed (HTTP $status): $(cat "$response_file")" >&2; exit 1 ;;
esac

echo "Synthetic rows, local Storage object, and local test bucket were cleaned up."
