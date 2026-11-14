#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
command -v psql >/dev/null 2>&1 || { echo "psql is required." >&2; exit 1; }
[[ "${ELORY_LOAD_TEST_CLEANUP:-}" == "YES" ]] || { echo "Set ELORY_LOAD_TEST_CLEANUP=YES to remove synthetic test rows." >&2; exit 1; }
case "$DATABASE_URL" in *dmttevcncsxzbamazmmq*) echo "SAFETY STOP: production cleanup is blocked." >&2; exit 1 ;; esac
[[ "$DATABASE_URL" == *127.0.0.1* || "$DATABASE_URL" == *localhost* ]] || { echo "LOCAL_DATABASE_URL must point to localhost." >&2; exit 1; }
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/test/cleanup-10000.sql
