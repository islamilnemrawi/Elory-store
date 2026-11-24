from pathlib import Path
import os
root = Path(os.environ["PROJECT_DIR"])
checks = {
    "order model carries internal code and wholesale price": (
        "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt",
        ("productCode", "wholesalePrice"),
    ),
    "Room entity carries internal fields": (
        "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt",
        ("productCode", "wholesalePrice"),
    ),
    "Supabase DTO accepts storefront aliases": (
        "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt",
        ('@Json(name = "name")', '@Json(name = "price")', '@Json(name = "image")',
         '@Json(name = "code")', '@Json(name = "wholesale_price")'),
    ),
    "order detail displays image, code, and wholesale price": (
        "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt",
        ("AsyncImage(", "كود المنتج:", "سعر الجملة:"),
    ),
    "repository maps snapshot data into order items": (
        "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt",
        ("item.productCode", "item.wholesalePrice", "item.productImage"),
    ),
}
failed = []
for label, (relative, needles) in checks.items():
    path = root / relative
    if not path.is_file():
        failed.append(f"{label}: file missing ({relative})")
        continue
    source = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in source]
    if missing:
        failed.append(f"{label}: missing {missing}")
    else:
        print(f"PASS: {label}")
if failed:
    print("\n".join("FAIL: " + item for item in failed))
    raise SystemExit(1)
print("All order-item display checks passed.")
