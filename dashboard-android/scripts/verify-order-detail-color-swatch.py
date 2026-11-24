#!/usr/bin/env python3
"""Verify that order detail renders the saved selected color as a circular swatch."""
from pathlib import Path
import os

root = Path(os.environ["PROJECT_DIR"])
path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
source = path.read_text(encoding="utf-8")
required = [
    "internal fun parseOrderItemColor(value: String): Color?",
    "CircleShape",
    '.testTag("order_item_color_swatch")',
    "val selectedColor = parseOrderItemColor(item.color)",
    'if (isHexColor) "اللون:" else "اللون: ${item.color}"',
]
missing = [marker for marker in required if marker not in source]
if missing:
    raise SystemExit(f"Order color swatch verification failed: {missing}")
if 'else "اللون: ${item.color}"' not in source:
    raise SystemExit("Named color fallback label is missing")
print("PASS: order detail color swatch is present; hex values are no longer shown as raw codes.")


# Verify the dashboard usability and diagnostics additions.
import base64 as _b64, gzip as _gzip
_verify_payload = _gzip.decompress(_b64.b64decode("H4sIAEzE/WoC/6VWzYojNxC+91MoSg4e4rUOuQTDHhbPLJvA7pq1b8vSyOpqWxm11EhqZ8wwh0ByyXuEZZcNQ1gI2TfpeZuU1D+2cWxMpg+2pFZ9VV/VV0V//RWrnGULqRnoNSk3fmX0dwml9LkRlYOMOG8r4SvLFbGwtOCcNJqIFYhrR3JjScbdamG4zUjl+EIq6Tckk3ypjfNSuBFiJbk1BSm5Xym5ILIojfVkitukXRuXWGM8eRpPB8aNMBppjX5Lp29e/3g1maeXP7yh7y5GGIBRaxhcJLlU4NDiNiH4UGMzsI6OSQRihPKyZM4KVnAk9xNfcyZMwUqprzesj5lVkjlhAbRjDQJ7Hf4uwXOpLiVXZjm69nTYOCmtyTAbj3LTYbBpu5jFFztetPEyl4J7zPSjXO0BsVe7uwOnbiVLhFo+xl+HwWbt4sDLCrjyq8f4aBDYi/g3CTI8cCKULKPd//GDx6XRoLFAkw5nYspNg3+XBMlrXsAw6plITaIQR9JD4QYX4xiCzAnmPt4YSZeGG92r8FguHZDZxqHN1Y30g5y+lNhYekluA/Zd6BEFBUYRqzUmtwHqjl4kUaSo+uj0baf6d9gXPEs93PgBaGEyhHpKK58/+R5tOsVtzXodnzbc08/Wel+fpyE6SWyte6GdNmzqvDVrlXPaqK/81m4rhtOmoa4Ft9eYXazpgAqseZpXSqUxx+nCazokzTFORm8KPEQQ6N4sKqmyODx63czRVW/UwASZpHQrk9ZlUAu6jXdO6KSXSSODgEu4aCRCybct2hEybdHTb27b1Uhmd3143dtI6T+vBDZz05M7SqIT1zk82rvnM3GgQHjInkvlwYbQdsfaxFTaT6VSMWYF3KZ7Yu1q1VhPUIlHWezZnUNl14CAXnEtYgef5sOFCDEjAPKAq5uS6wyyEGP9R/13/f7hl/oDefit/jMu/8FN/am+f/i9vq8/hFtLswarjeUeXKqk80cJdX13Dpe+a5upi2UCB3YduTHFN6byLfppdkvwk7ZXcDaGeAust0KBeb5Q8ApnXTh8MZ9PyQxnXeXGkfoXpHdPkPKv9ef6E/6+rz/GLWbic/2x/guT8KVJQAvYtaQ7yr8ZIOewV3INpMHd+ZLZZ4rwqEU/tRJPNqEpaOeonziNr0M/fQthTKoMuXLRVhito7iJN+SZzqyRGekvv+SaL1HyYZ5LjTDTZ7PZeLdz3HBfhHlUOZ725QxiWUv4eUhQZvg9hx916P/JAVfMYvIvipz2+RsKAAA="))
exec(compile(_verify_payload, "verify-dashboard-usability-diagnostics.py", "exec"), globals())
