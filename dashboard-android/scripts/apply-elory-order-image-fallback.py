from pathlib import Path
import os

root = Path(os.environ["PROJECT_DIR"]).resolve()
path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"
source = path.read_text(encoding="utf-8")

old_import = "import coil.compose.AsyncImage"
new_import = "import coil.compose.SubcomposeAsyncImage"
if old_import in source:
    if source.count(old_import) != 1:
        raise SystemExit("Ambiguous Coil image import; refusing to edit.")
    source = source.replace(old_import, new_import, 1)
elif new_import not in source:
    raise SystemExit("Order detail image component import was not found.")

old_block = '''                                    AsyncImage(
                                        model = item.imageUrl,
                                        contentDescription = item.productName,
                                        modifier = Modifier.size(64.dp).clip(RoundedCornerShape(10.dp)),
                                        contentScale = ContentScale.Crop
                                    )'''
new_block = '''                                    SubcomposeAsyncImage(
                                        model = item.imageUrl,
                                        contentDescription = item.productName,
                                        modifier = Modifier.size(64.dp).clip(RoundedCornerShape(10.dp)),
                                        contentScale = ContentScale.Crop,
                                        loading = {
                                            Box(
                                                modifier = Modifier.fillMaxSize()
                                                    .background(MaterialTheme.colorScheme.surfaceVariant),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                CircularProgressIndicator(
                                                    modifier = Modifier.size(20.dp),
                                                    strokeWidth = 2.dp
                                                )
                                            }
                                        },
                                        error = {
                                            Box(
                                                modifier = Modifier.fillMaxSize()
                                                    .background(MaterialTheme.colorScheme.surfaceVariant),
                                                contentAlignment = Alignment.Center
                                            ) {
                                                Icon(
                                                    Icons.Outlined.Image,
                                                    contentDescription = "صورة المنتج غير متاحة",
                                                    tint = MaterialTheme.colorScheme.onSurfaceVariant
                                                )
                                            }
                                        }
                                    )'''
if old_block in source:
    if source.count(old_block) != 1:
        raise SystemExit("Ambiguous order image component; refusing to edit.")
    source = source.replace(old_block, new_block, 1)
elif new_block not in source:
    raise SystemExit("Order image component differs from the reviewed source; refusing a blind patch.")

path.write_text(source, encoding="utf-8")

verified = path.read_text(encoding="utf-8")
for marker in ("SubcomposeAsyncImage(", "loading = {", "error = {", "صورة المنتج غير متاحة"):
    if marker not in verified:
        raise SystemExit("Order image fallback verification failed: " + marker)
print("PASS: order item images now show a loading state and a graceful fallback on failed downloads.")
