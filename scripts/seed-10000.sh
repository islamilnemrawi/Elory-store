#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:54322/postgres}"
command -v psql >/dev/null 2>&1 || { echo "psql is required." >&2; exit 1; }
[[ "${ELORY_LOAD_TEST_APPROVED:-}" == "YES" ]] || { echo "Set ELORY_LOAD_TEST_APPROVED=YES only for a disposable local database." >&2; exit 1; }
case "$DATABASE_URL" in *dmttevcncsxzbamazmmq*) echo "SAFETY STOP: production seeding is blocked." >&2; exit 1 ;; esac
[[ "$DATABASE_URL" == *127.0.0.1* || "$DATABASE_URL" == *localhost* ]] || { echo "LOCAL_DATABASE_URL must point to localhost." >&2; exit 1; }
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/test/seed-10000.sql

# Upload a generated image into the local-only public Storage bucket.
if [[ -f "supabase/.env.test" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "supabase/.env.test"
  set +a
fi
SUPABASE_URL="${SUPABASE_URL:-http://127.0.0.1:54321}"
command -v curl >/dev/null 2>&1 || { echo "curl is required to upload the local image fixture." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required to generate the local PNG fixture." >&2; exit 1; }
[[ -n "${SUPABASE_SERVICE_ROLE_KEY:-}" ]] || { echo "Set SUPABASE_SERVICE_ROLE_KEY in supabase/.env.test or the environment." >&2; exit 1; }
[[ "$SUPABASE_URL" == *127.0.0.1* || "$SUPABASE_URL" == *localhost* ]] || { echo "SAFETY STOP: image upload URL must be localhost." >&2; exit 1; }

IMAGE_FILE="$(mktemp)"
trap 'rm -f "$IMAGE_FILE"' EXIT
python3 - "$IMAGE_FILE" <<'PY'
import struct, sys, zlib
width = height = 512
rows = []
for y in range(height):
    row = bytearray([0])
    for x in range(width):
        row.extend(((x * 3 + y) % 256, (y * 2 + x // 2) % 256, (x + y * 2) % 256))
    rows.append(row)
def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
png = b"\x89PNG\r\n\x1a\n"
png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(b"".join(rows), 6))
png += chunk(b"IEND", b"")
with open(sys.argv[1], "wb") as output:
    output.write(png)
PY
curl --fail --silent --show-error -X POST "$SUPABASE_URL/storage/v1/object/elory-load-test/product.png" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Content-Type: image/png" \
  -H "x-upsert: true" \
  --data-binary "@$IMAGE_FILE"
echo "Uploaded the synthetic 512x512 PNG to local Supabase Storage."
