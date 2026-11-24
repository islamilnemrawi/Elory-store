#!/usr/bin/env python3
"""Add owner-PIN protected deletion of Elory Prime subscriptions to the dashboard."""
from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()
PKG = ROOT / "app/src/main/java/com/pinky/dashboard"

def patch(relative: str, old: str, new: str, label: str) -> None:
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing required source file for {label}: {relative}")
    source = path.read_text(encoding="utf-8")
    if new in source:
        print(f"Already applied: {label}")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"Expected exactly one anchor for {label}; found {count}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"PASS: {label}")

VM = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
PRIME = "app/src/main/java/com/pinky/dashboard/ui/screens/prime/PrimeScreen.kt"
APP = "app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt"

# Extend the existing PIN-protected RPC allow-list without removing products support.
patch(
    VM,
    'if (scope !in setOf("orders", "customers", "coupons", "products")) {',
    'if (scope !in setOf("orders", "customers", "coupons", "products", "prime")) {',
    "allow Prime in owner deletion RPC"
)

# Refresh the in-memory Prime list only after the remote delete has succeeded.
patch(
    VM,
'''                "products" -> {
                    val refresh = productRepository.syncProducts()
                    if (refresh.isFailure) android.util.Log.w("OwnerDataReset", "Products deleted remotely; local refresh will retry", refresh.exceptionOrNull())
                }
''',
'''                "products" -> {
                    val refresh = productRepository.syncProducts()
                    if (refresh.isFailure) android.util.Log.w("OwnerDataReset", "Products deleted remotely; local refresh will retry", refresh.exceptionOrNull())
                }
                "prime" -> {
                    _primeSubscribers.value = if (ids == null) emptyList() else _primeSubscribers.value.filterNot { it.id in ids }
                    try {
                        refreshPrimeSubscribers()
                    } catch (refreshError: Exception) {
                        android.util.Log.w("OwnerDataReset", "Prime subscriptions deleted remotely; list refresh will retry", refreshError)
                    }
                }
''',
    "refresh Prime list after remote deletion"
)

# Add owner-only selection controls to the existing Prime screen.
patch(
    PRIME,
    "import com.pinky.dashboard.ui.theme.StatusCancelled",
    "import com.pinky.dashboard.ui.theme.StatusCancelled\nimport com.pinky.dashboard.ui.components.OwnerDataResetControls",
    "Prime screen owner-delete controls import"
)
patch(
    PRIME,
'''    onToggleStatus: (String, Boolean) -> Unit,
    modifier: Modifier = Modifier
) {
    var searchQuery by remember { mutableStateOf("") }
    var showAddDialog by remember { mutableStateOf(false) }
''',
'''    onToggleStatus: (String, Boolean) -> Unit,
    isPrimaryOwner: Boolean = false,
    onDeleteSelected: suspend (List<String>?, String) -> Result<Int> = { _, _ -> Result.failure(IllegalStateException("غير متاح")) },
    onSetDataResetPin: suspend (String) -> Result<Unit> = { Result.failure(IllegalStateException("غير متاح")) },
    modifier: Modifier = Modifier
) {
    var searchQuery by remember { mutableStateOf("") }
    var showAddDialog by remember { mutableStateOf(false) }
    var selectedPrimeSubscriptionIds by remember { mutableStateOf(setOf<String>()) }
    var isPrimeDeleteMode by remember { mutableStateOf(false) }
''',
    "Prime screen deletion state and callbacks"
)
patch(
    PRIME,
    '''            // 3. Search and Filters Header
            item {
''',
    '''            // Owner-only, PIN-protected deletion is limited to the selected Prime subscription rows.
            item {
                if (isPrimaryOwner) {
                    OwnerDataResetControls(
                        scopeLabel = "اشتراكات Elory Prime",
                        isPrimaryOwner = isPrimaryOwner,
                        isDeleteMode = isPrimeDeleteMode,
                        selectedIds = selectedPrimeSubscriptionIds.filter { id -> filteredSubscribers.any { it.id == id } },
                        totalCount = filteredSubscribers.size,
                        onEnterDeleteMode = { isPrimeDeleteMode = true },
                        onExitDeleteMode = { isPrimeDeleteMode = false; selectedPrimeSubscriptionIds = emptySet() },
                        onSelectAll = { selectedPrimeSubscriptionIds = filteredSubscribers.map { it.id }.toSet() },
                        onClearSelection = { selectedPrimeSubscriptionIds = emptySet() },
                        onDeleteSelected = onDeleteSelected,
                        onSetPin = onSetDataResetPin,
                        onDeleteComplete = { selectedPrimeSubscriptionIds = emptySet(); isPrimeDeleteMode = false },
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                }
            }

            // 3. Search and Filters Header
            item {
''',
    "Prime subscriber deletion toolbar"
)
patch(
    PRIME,
    '''                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column {
                                    Text(subscriber.customerName, fontWeight = FontWeight.Bold, fontSize = 16.sp)
''',
    '''                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                if (isPrimaryOwner && isPrimeDeleteMode) {
                                    Checkbox(
                                        checked = selectedPrimeSubscriptionIds.contains(subscriber.id),
                                        onCheckedChange = { checked ->
                                            selectedPrimeSubscriptionIds = if (checked) {
                                                selectedPrimeSubscriptionIds + subscriber.id
                                            } else {
                                                selectedPrimeSubscriptionIds - subscriber.id
                                            }
                                        }
                                    )
                                }
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(subscriber.customerName, fontWeight = FontWeight.Bold, fontSize = 16.sp)
''',
    "Prime subscriber selection checkbox"
)
patch(
    APP,
'''                                PrimeScreen(
                                    subscribers = primeSubscribers,
                                    onGrantPrime = { email, days -> viewModel.grantPrimeByEmail(email, days) },
                                    onToggleStatus = { id, active -> viewModel.togglePrimeStatus(id, active) }
                                )
''',
'''                                PrimeScreen(
                                    subscribers = primeSubscribers,
                                    onGrantPrime = { email, days -> viewModel.grantPrimeByEmail(email, days) },
                                    onToggleStatus = { id, active -> viewModel.togglePrimeStatus(id, active) },
                                    isPrimaryOwner = isPrimaryOwner,
                                    onDeleteSelected = { ids, pin -> viewModel.deleteOwnerData("prime", ids, pin) },
                                    onSetDataResetPin = { pin -> viewModel.setOwnerDataResetPin(pin) }
                                )
''',
    "wire Prime deletion to owner PIN RPC"
)

# Fail fast if a future source change silently disconnects any part of this feature.
checks = {
    VM: ('"prime" -> {', 'ids = ids'),
    PRIME: ('scopeLabel = "اشتراكات Elory Prime"', 'selectedPrimeSubscriptionIds.contains(subscriber.id)', 'onDeleteSelected = onDeleteSelected'),
    APP: ('viewModel.deleteOwnerData("prime", ids, pin)', 'isPrimaryOwner = isPrimaryOwner')
}
for relative, markers in checks.items():
    source = (ROOT / relative).read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise SystemExit(f"Prime deletion wiring verification failed in {relative}: {missing}")
print("PASS: Prime deletion is owner-only, PIN-protected, selection-based, and remotely refreshed.")
