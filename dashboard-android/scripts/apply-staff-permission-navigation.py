from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()
P = "app/src/main/java/com/pinky/dashboard/"
APP = P + "ui/PinkyApp.kt"
NAV = P + "ui/navigation/DashboardSection.kt"
NAV_UI = P + "ui/components/PinkyNavigationComponents.kt"
AUTH = P + "domain/model/AuthModels.kt"
REPO = P + "data/repository/RepositoriesImpl.kt"
VM = P + "ui/PinkyViewModel.kt"
STAFF = P + "ui/screens/staff/StaffScreen.kt"
OFFERS = P + "ui/screens/offers/OffersScreen.kt"
QUICK = P + "ui/components/QuickActionsDialog.kt"

def one(path, old, new, label):
    f = ROOT / path
    s = f.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one anchor, found {n}")
    f.write_text(s.replace(old, new, 1), encoding="utf-8")

def many(path, old, new, n, label):
    f = ROOT / path
    s = f.read_text(encoding="utf-8")
    found = s.count(old)
    if found != n:
        raise SystemExit(f"{label}: expected {n} anchors, found {found}")
    f.write_text(s.replace(old, new), encoding="utf-8")

one(AUTH,
'''    val permissions: Set<Permission> = Permission.defaultPermissionsFor(role)
) {
    fun hasPermission(permission: Permission): Boolean {
        return role == UserRole.OWNER || permissions.contains(permission)
    }''',
'''    val permissions: Set<Permission> = emptySet()
) {
    fun hasPermission(permission: Permission): Boolean = permissions.contains(permission)''',
"Remove role-based permission bypass")

one(NAV,
'''    val requiredPermission: Permission? = null,
    val isPrimaryBottomNav: Boolean = false
) {''',
'''    val requiredPermission: Permission? = null,
    val isPrimaryBottomNav: Boolean = false,
    val additionalRequiredPermissions: Set<Permission> = emptySet()
) {''', "Add section permission metadata")
one(NAV,
'''    OFFERS_COUPONS("offers_coupons", "العروض والكوبونات", Icons.Outlined.LocalOffer, Permission.MANAGE_OFFERS),''',
'''    OFFERS_COUPONS("offers_coupons", "العروض والكوبونات", Icons.Outlined.LocalOffer, Permission.MANAGE_OFFERS, additionalRequiredPermissions = setOf(Permission.MANAGE_COUPONS)),''', "Allow either offers or coupons permission")
one(NAV,
'''    REPORTS("reports", "التقارير والأرباح", Icons.Outlined.BarChart, Permission.VIEW_ANALYTICS),''',
'''    REPORTS("reports", "التقارير والأرباح", Icons.Outlined.BarChart, Permission.VIEW_ANALYTICS, additionalRequiredPermissions = setOf(Permission.VIEW_PROFIT)),''', "Allow analytics or profit permission")
one(NAV,
'''    HEALTH_CHECK("health_check", "فحص النظام والربط", Icons.Outlined.CheckCircle, null),
    SETTINGS("settings", "الإعدادات", Icons.Outlined.Settings, null, isPrimaryBottomNav = true);''',
'''    HEALTH_CHECK("health_check", "فحص النظام والربط", Icons.Outlined.CheckCircle, Permission.MANAGE_SETTINGS),
    SETTINGS("settings", "الإعدادات", Icons.Outlined.Settings, Permission.MANAGE_SETTINGS, isPrimaryBottomNav = true);''', "Gate diagnostics and settings")
one(NAV,
'''    SETTINGS("settings", "الإعدادات", Icons.Outlined.Settings, Permission.MANAGE_SETTINGS, isPrimaryBottomNav = true);''',
'''    SETTINGS("settings", "الإعدادات", Icons.Outlined.Settings, Permission.MANAGE_SETTINGS, isPrimaryBottomNav = true);

    fun isAccessibleBy(user: com.pinky.dashboard.domain.model.AdminUser?): Boolean {
        val required = listOfNotNull(requiredPermission) + additionalRequiredPermissions
        return required.isEmpty() || required.any { user?.hasPermission(it) == true }
    }''', "Add common section access check")

one(NAV_UI,
'''    val allowedSections = sections.filter { s ->
        s.requiredPermission == null || currentUser?.hasPermission(s.requiredPermission) == true
    }''',
'''    val allowedSections = sections.filter { section -> section.isAccessibleBy(currentUser) }''', "Filter drawer items")
one(NAV_UI,
'''    val visibleSections = DashboardSection.entries.filter { section ->
        section.requiredPermission == null || currentUser?.hasPermission(section.requiredPermission) == true
    }''',
'''    val visibleSections = DashboardSection.entries.filter { section -> section.isAccessibleBy(currentUser) }''', "Filter bottom navigation")
one(NAV_UI,
'''    onNotificationsClick: () -> Unit,
    isRefreshing: Boolean = false,''',
'''    onNotificationsClick: () -> Unit,
    canViewNotifications: Boolean = true,
    isRefreshing: Boolean = false,''', "Add notification capability to top bar")
old_bell = '''            // Notifications Bell
            IconButton(
                onClick = onNotificationsClick,
                modifier = Modifier.testTag("top_bar_notif_btn")
            ) {
                if (unreadNotificationsCount > 0) {
                    BadgedBox(
                        badge = {
                            Badge(containerColor = MaterialTheme.colorScheme.primary) {
                                Text("$unreadNotificationsCount", color = MaterialTheme.colorScheme.onPrimary)
                            }
                        }
                    ) {
                        Icon(
                            imageVector = Icons.Outlined.Notifications,
                            contentDescription = "الإشعارات",
                            tint = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                } else {
                    Icon(
                        imageVector = Icons.Outlined.Notifications,
                        contentDescription = "الإشعارات",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
'''
new_bell = '''            // Notifications Bell — hidden without the assigned capability.
            if (canViewNotifications) {
                IconButton(
                    onClick = onNotificationsClick,
                    modifier = Modifier.testTag("top_bar_notif_btn")
                ) {
                    if (unreadNotificationsCount > 0) {
                        BadgedBox(
                            badge = {
                                Badge(containerColor = MaterialTheme.colorScheme.primary) {
                                    Text("$unreadNotificationsCount", color = MaterialTheme.colorScheme.onPrimary)
                                }
                            }
                        ) {
                            Icon(Icons.Outlined.Notifications, contentDescription = "الإشعارات", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    } else {
                        Icon(Icons.Outlined.Notifications, contentDescription = "الإشعارات", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
'''
one(NAV_UI, old_bell, new_bell, "Hide notification bell")

one(QUICK,
'''fun QuickActionsDialog(
    onDismiss: () -> Unit,
    onSelectAction: (DashboardSection) -> Unit,
    modifier: Modifier = Modifier
) {''',
'''fun QuickActionsDialog(
    onDismiss: () -> Unit,
    onSelectAction: (DashboardSection) -> Unit,
    visibleSections: Set<DashboardSection> = DashboardSection.entries.toSet(),
    modifier: Modifier = Modifier
) {''', "Add visible destinations to quick actions")
one(QUICK,
'''        QuickActionItem("تحرير الموقع", "التعديل البصري للمتجر", Icons.Outlined.Web, DashboardSection.WEBSITE_EDITOR)
    )''',
'''        QuickActionItem("تحرير الموقع", "التعديل البصري للمتجر", Icons.Outlined.Web, DashboardSection.WEBSITE_EDITOR)
    ).filter { it.targetSection in visibleSections }''', "Filter quick action destinations")

one(REPO,
'''            "admin", "administrator", "manager" -> UserRole.ADMIN''',
'''            "admin", "administrator" -> UserRole.ADMIN
            "manager" -> UserRole.MANAGER''', "Preserve manager display label")
one(REPO,
'''        val permissions = if (role == UserRole.OWNER) {
            Permission.entries.toSet()
        } else {
            profile.permissions.orEmpty()
                .filterValues { it }
                .keys
                .mapNotNull { Permission.fromStorageKey(it) }
                .toSet()
        }''',
'''        val permissions = profile.permissions.orEmpty()
            .filterValues { it }
            .keys
            .mapNotNull { Permission.fromStorageKey(it) }
            .filterNot { it == Permission.MANAGE_STAFF }
            .toSet()''', "Load only explicit staff permissions")
one(REPO,
'''        _currentUser.value = current.copy(role = role, permissions = Permission.defaultPermissionsFor(role))''',
'''        _currentUser.value = current.copy(role = role, permissions = current.permissions)''', "Keep debug role preview permission-neutral")
one(VM,
'''                                Permission.fromStorageKey(it)
                            }?.toSet() ?: emptySet(),''',
'''                                Permission.fromStorageKey(it)
                            }?.filterNot { it == Permission.MANAGE_STAFF }?.toSet() ?: emptySet(),''', "Remove reserved staff permission from listed staff")

one(STAFF,
'''                                onClick = {
                                    role = r
                                    selectedPermissions = Permission.defaultPermissionsFor(r)
                                },''',
'''                                onClick = { role = r },''', "Keep role label separate from permission selection")
one(STAFF,
'''                    Permission.entries.forEach { perm ->''',
'''                    Permission.entries.filterNot { it == Permission.MANAGE_STAFF }.forEach { perm ->''', "Hide staff-management permission checkbox")
one(STAFF,
'''            staff?.permissions ?: setOf(Permission.VIEW_DASHBOARD, Permission.MANAGE_ORDERS)''',
'''            staff?.permissions?.minus(Permission.MANAGE_STAFF) ?: setOf(Permission.VIEW_DASHBOARD, Permission.MANAGE_ORDERS)''', "Ignore legacy staff-management permission")
one(STAFF,
'''                                        permissions = selectedPermissions,''',
'''                                        permissions = selectedPermissions - Permission.MANAGE_STAFF,''', "Never save staff-management permission to employees")
one(STAFF,
'''    isPrimaryOwner: Boolean = false,
    onResetStaffPassword:''',
'''    isPrimaryOwner: Boolean = false,
    currentUserId: String? = null,
    onResetStaffPassword:''', "Identify signed-in owner in staff screen")
one(STAFF,
'''                                if (isPrimaryOwner && staff.role != UserRole.OWNER) {''',
'''                                if (isPrimaryOwner && staff.id != currentUserId) {''', "Allow reset for Owner-labelled staff")

one(OFFERS,
'''    websiteSaveState: String = "idle",
    ''',
'''    websiteSaveState: String = "idle",
    canManageOffers: Boolean = true,
    canManageCoupons: Boolean = true,
    ''', "Add offers and coupons permissions")
one(OFFERS,
'''    var selectedTab by remember { mutableIntStateOf(0) } // 0 = Offers/Banners, 1 = Coupons''',
'''    var selectedTab by remember(canManageOffers, canManageCoupons) { mutableIntStateOf(if (canManageOffers) 0 else 1) } // 0 = Offers/Banners, 1 = Coupons''', "Select an allowed default tab")
one(OFFERS,
'''            if (selectedTab == 1) ExtendedFloatingActionButton(''',
'''            if (selectedTab == 1 && canManageCoupons) ExtendedFloatingActionButton(''', "Hide coupon creation without permission")
old_tabs = '''            // Tab Selector
            TabRow(
                selectedTabIndex = selectedTab,
                containerColor = MaterialTheme.colorScheme.surface,
                contentColor = PinkPrimary
            ) {
                Tab(
                    selected = selectedTab == 0,
                    onClick = { selectedTab = 0 },
                    text = { Text("البنرات والهيرو", fontWeight = FontWeight.Bold) },
                    icon = { Icon(Icons.Outlined.LocalOffer, contentDescription = null) }
                )
                Tab(
                    selected = selectedTab == 1,
                    onClick = { selectedTab = 1 },
                    text = { Text("كوبونات الخصم (${coupons.size})", fontWeight = FontWeight.Bold) },
                    icon = { Icon(Icons.Outlined.Discount, contentDescription = null) }
                )
            }
'''
new_tabs = '''            // Only show the tab selector when both capabilities are granted.
            if (canManageOffers && canManageCoupons) {
                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = MaterialTheme.colorScheme.surface,
                    contentColor = PinkPrimary
                ) {
                    Tab(
                        selected = selectedTab == 0,
                        onClick = { selectedTab = 0 },
                        text = { Text("البنرات والهيرو", fontWeight = FontWeight.Bold) },
                        icon = { Icon(Icons.Outlined.LocalOffer, contentDescription = null) }
                    )
                    Tab(
                        selected = selectedTab == 1,
                        onClick = { selectedTab = 1 },
                        text = { Text("كوبونات الخصم (${coupons.size})", fontWeight = FontWeight.Bold) },
                        icon = { Icon(Icons.Outlined.Discount, contentDescription = null) }
                    )
                }
            }
'''
one(OFFERS, old_tabs, new_tabs, "Hide unauthorized inner tab")

one(APP,
'''import com.pinky.dashboard.domain.model.OrderStatus
''',
'''import com.pinky.dashboard.domain.model.OrderStatus
import com.pinky.dashboard.domain.model.Permission
''', "Import permission model")
app_file = ROOT / APP
s = app_file.read_text(encoding="utf-8")
for old, new in [
    ('viewModel.selectSection(section)', 'navigateToSection(section)'),
    ('viewModel.selectSection(it)', 'navigateToSection(it)'),
    ('viewModel.selectSection(DashboardSection.NOTIFICATIONS)', 'navigateToSection(DashboardSection.NOTIFICATIONS)'),
    ('viewModel.selectSection(DashboardSection.ORDERS)', 'navigateToSection(DashboardSection.ORDERS)'),
    ('viewModel.selectSection(DashboardSection.PRODUCTS)', 'navigateToSection(DashboardSection.PRODUCTS)'),
    ('viewModel.selectSection(DashboardSection.CUSTOMERS)', 'navigateToSection(DashboardSection.CUSTOMERS)'),
    ('viewModel.selectSection(DashboardSection.OFFERS_COUPONS)', 'navigateToSection(DashboardSection.OFFERS_COUPONS)'),
    ('viewModel.selectSection(DashboardSection.SETTINGS)', 'navigateToSection(DashboardSection.SETTINGS)'),
]:
    s = s.replace(old, new)
app_file.write_text(s, encoding="utf-8")
one(APP,
'''    val snackbarHostState = remember { SnackbarHostState() }
''',
'''    val snackbarHostState = remember { SnackbarHostState() }
    val effectiveUser = remember(currentUser, isPrimaryOwner) {
        currentUser?.let { user ->
            user.copy(
                permissions = if (isPrimaryOwner) Permission.entries.toSet()
                else user.permissions - Permission.MANAGE_STAFF
            )
        }
    }
    val canAccessSection: (DashboardSection) -> Boolean = remember(effectiveUser?.permissions, isPrimaryOwner) {
        { section -> section.isAccessibleBy(effectiveUser) }
    }
    val navigateToSection: (DashboardSection) -> Unit = { section ->
        if (canAccessSection(section)) {
            viewModel.selectSection(section)
        } else {
            DashboardSection.entries.firstOrNull { canAccessSection(it) }?.let(viewModel::selectSection)
            coroutineScope.launch { snackbarHostState.showSnackbar("ليس لديك صلاحية الوصول إلى هذا القسم.") }
        }
    }
    LaunchedEffect(currentSection, effectiveUser?.permissions, isPrimaryOwner) {
        if (!canAccessSection(currentSection)) {
            DashboardSection.entries.firstOrNull { canAccessSection(it) }?.let(viewModel::selectSection)
        }
        if (!canAccessSection(DashboardSection.ORDERS)) viewModel.selectOrder(null)
    }
''', "Add effective permissions and route guard")
one(APP,
'''    LaunchedEffect(initialOrderId) {
        if (initialOrderId != null) {
            viewModel.selectOrderById(initialOrderId)
        }
    }''',
'''    LaunchedEffect(initialOrderId, effectiveUser?.permissions, isPrimaryOwner) {
        if (initialOrderId != null && canAccessSection(DashboardSection.ORDERS)) {
            viewModel.selectOrderById(initialOrderId)
        }
    }''', "Guard order notification deep links")
many(APP, 'currentUser = currentUser,', 'currentUser = effectiveUser,', 7, "Pass effective permissions to screens")
one(APP,
'''                            onOpenDrawer = { coroutineScope.launch { drawerState.open() } },
                            currentUser = currentUser
''',
'''                            onOpenDrawer = { coroutineScope.launch { drawerState.open() } },
                            currentUser = effectiveUser
''', "Pass effective permissions to bottom navigation")
one(APP,
'''                                HealthCheckScreen(
                                    currentUser = currentUser
''',
'''                                HealthCheckScreen(
                                    currentUser = effectiveUser
''', "Pass effective permissions to diagnostics")
one(APP,
'''                            onNotificationsClick = { navigateToSection(DashboardSection.NOTIFICATIONS) },
''',
'''                            onNotificationsClick = { navigateToSection(DashboardSection.NOTIFICATIONS) },
                            canViewNotifications = effectiveUser?.hasPermission(Permission.VIEW_NOTIFICATIONS) == true,
''', "Hide notification shortcut without permission")
one(APP,
'''                                    canAssignElevatedRoles = currentUser?.role == UserRole.OWNER,''',
'''                                    canAssignElevatedRoles = isPrimaryOwner,''', "Only primary owner can assign role labels")
one(APP,
'''                                    isPrimaryOwner = isPrimaryOwner,
                                    onResetStaffPassword =''',
'''                                    isPrimaryOwner = isPrimaryOwner,
                                    currentUserId = currentUser?.id,
                                    onResetStaffPassword =''', "Pass primary-owner identity to staff controls")
one(APP,
'''                                    websiteSaveState = websiteSaveState
''',
'''                                    websiteSaveState = websiteSaveState,
                                    canManageOffers = effectiveUser?.hasPermission(Permission.MANAGE_OFFERS) == true,
                                    canManageCoupons = effectiveUser?.hasPermission(Permission.MANAGE_COUPONS) == true
''', "Pass independent offers and coupons permissions")
one(APP,
'''                                    canManageCoupons = effectiveUser?.hasPermission(Permission.MANAGE_COUPONS) == true
                                ,''',
'''                                    canManageCoupons = effectiveUser?.hasPermission(Permission.MANAGE_COUPONS) == true,''', "Format offers permission arguments")
many(APP,
'''                                    onSelectOrder = { viewModel.selectOrder(it) },''',
'''                                    onSelectOrder = { if (canAccessSection(DashboardSection.ORDERS)) viewModel.selectOrder(it) },''', 2, "Guard dashboard and order selection callbacks")
one(APP,
'''                                                notif.targetOrderId?.let { viewModel.selectOrderById(it) }
                                                    ?: navigateToSection(DashboardSection.ORDERS)''',
'''                                                if (canAccessSection(DashboardSection.ORDERS)) {
                                                    notif.targetOrderId?.let { viewModel.selectOrderById(it) }
                                                        ?: navigateToSection(DashboardSection.ORDERS)
                                                } else {
                                                    navigateToSection(DashboardSection.ORDERS)
                                                }''', "Guard notification links to orders")
one(APP,
'''                    orders = orders,
                    products = products,
                    customers = customers,
                    categories = categories,
                    coupons = coupons,''',
'''                    orders = if (canAccessSection(DashboardSection.ORDERS)) orders else emptyList(),
                    products = if (canAccessSection(DashboardSection.PRODUCTS)) products else emptyList(),
                    customers = if (canAccessSection(DashboardSection.CUSTOMERS)) customers else emptyList(),
                    categories = if (canAccessSection(DashboardSection.CATEGORIES)) categories else emptyList(),
                    coupons = if (effectiveUser?.hasPermission(Permission.MANAGE_COUPONS) == true) coupons else emptyList(),''', "Filter global search data")
one(APP,
'''                        viewModel.selectOrder(order)''',
'''                        if (canAccessSection(DashboardSection.ORDERS)) viewModel.selectOrder(order)''', "Guard order search result")
one(APP,
'''                    onSelectAction = { section ->
                        showQuickActionsDialog = false
                        navigateToSection(section)
                    }
''',
'''                    onSelectAction = { section ->
                        showQuickActionsDialog = false
                        navigateToSection(section)
                    },
                    visibleSections = DashboardSection.entries.filter { canAccessSection(it) }.toSet()
''', "Filter quick action shortcuts")
one(APP,
'''                    orders = orders,
                    products = products,
                    customers = customers,
                    analytics = analytics,
                    currentUser = effectiveUser,''',
'''                    orders = if (canAccessSection(DashboardSection.ORDERS)) orders else emptyList(),
                    products = if (canAccessSection(DashboardSection.PRODUCTS)) products else emptyList(),
                    customers = if (canAccessSection(DashboardSection.CUSTOMERS)) customers else emptyList(),
                    analytics = if (effectiveUser?.hasPermission(Permission.VIEW_ANALYTICS) == true) analytics else com.pinky.dashboard.domain.model.AnalyticsData(),
                    currentUser = effectiveUser,''', "Filter AI assistant data")
one(APP,
'''            selectedOrder?.let { order ->''',
'''            if (canAccessSection(DashboardSection.ORDERS)) selectedOrder?.let { order ->''', "Guard order details overlay")
one(APP,
'''                    canViewWholesale = currentUser?.canViewWholesale == true,
                    canViewInternalCode = currentUser?.canViewInternalCode == true,''',
'''                    canViewWholesale = effectiveUser?.canViewWholesale == true,
                    canViewInternalCode = effectiveUser?.canViewInternalCode == true,''', "Use effective permissions in order details")
one(APP,
'''                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                            .background(MaterialTheme.colorScheme.background)
                    ) {
                        when (currentSection) {''',
'''                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(innerPadding)
                            .background(MaterialTheme.colorScheme.background)
                    ) {
                        if (!canAccessSection(currentSection)) {
                            Column(
                                modifier = Modifier.fillMaxSize().padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center
                            ) {
                                Text("لا توجد صلاحيات مخصصة لحسابك حاليًا.", style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurface)
                                Text("تواصل مع المالك الرئيسي لتحديد الأقسام المسموح لك بالوصول إليها.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        } else when (currentSection) {''', "Block unauthorized screen content")

checks = {
    "role labels do not grant permissions": "permissions.contains(permission)" in (ROOT / AUTH).read_text(encoding="utf-8"),
    "owner role does not synthesize all permissions": "val permissions = if (role == UserRole.OWNER)" not in (ROOT / REPO).read_text(encoding="utf-8"),
    "staff management is not assignable": "Permission.entries.filterNot { it == Permission.MANAGE_STAFF }" in (ROOT / STAFF).read_text(encoding="utf-8"),
    "drawer is permission-filtered": "section.isAccessibleBy(currentUser)" in (ROOT / NAV_UI).read_text(encoding="utf-8"),
    "bottom bar is permission-filtered": (ROOT / NAV_UI).read_text(encoding="utf-8").count("section.isAccessibleBy(currentUser)") == 2,
    "route guard is installed": "if (!canAccessSection(currentSection))" in (ROOT / APP).read_text(encoding="utf-8"),
    "quick actions are filtered": "visibleSections = DashboardSection.entries.filter" in (ROOT / APP).read_text(encoding="utf-8"),
    "notification bell is filtered": "if (canViewNotifications)" in (ROOT / NAV_UI).read_text(encoding="utf-8"),
    "role selection preserves permissions": "onClick = { role = r }" in (ROOT / STAFF).read_text(encoding="utf-8"),
    "offers and coupons tabs are separate": "canManageOffers && canManageCoupons" in (ROOT / OFFERS).read_text(encoding="utf-8"),
}
for label, ok in checks.items():
    if not ok:
        raise SystemExit("Permission navigation regression: " + label)
    print("PASS:", label)
