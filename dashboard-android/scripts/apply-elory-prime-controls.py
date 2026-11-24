from __future__ import annotations
import os
from pathlib import Path
ROOT = Path(os.environ["PROJECT_DIR"]).resolve()
def patch(relative: str, old: str, new: str, label: str) -> None:
    path = ROOT / relative
    if not path.is_file(): raise SystemExit(f"Missing required source file for {label}: {relative}")
    source = path.read_text(encoding="utf-8")
    count = source.count(old)
    if count == 0 and new in source:
        print(f"Already applied: {label}"); return
    if count != 1: raise SystemExit(f"Expected exactly one anchor for {label}; found {count}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"PASS: {label}")
MODEL = "app/src/main/java/com/pinky/dashboard/domain/model/StoreModels.kt"
JSON = "app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt"
VM = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
EDITOR = "app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"
MOCKUP = "app/src/main/java/com/pinky/dashboard/ui/screens/website/PhoneMockupView.kt"
patch(MODEL,
    '    val primeThemeFeature: String = "ثيم برونزي فخم",\n    val primeButtonText: String = "اشتركي الآن",',
    '    val primeThemeFeature: String = "ثيم برونزي فخم",\n    val primeExtraFeatures: List<String> = emptyList(),\n    val primeButtonText: String = "اشتركي الآن",',
    "Prime extra-features model")
patch(JSON,
    '    @Json(name = "freeShippingOrdersCount") val freeShippingOrdersCount: Int = 4,\n    @Json(name = "packagingFeature") val packagingFeature: String = "تغليف مميز مجاني",\n    @Json(name = "themeFeature") val themeFeature: String = "ثيم برونزي فخم",',
    '    @Json(name = "freeShippingOrdersCount") val freeShippingOrdersCount: Int = 6,\n    @Json(name = "packagingFeature") val packagingFeature: String = "تغليف مميز مجاني",\n    @Json(name = "themeFeature") val themeFeature: String = "ثيم برونزي فخم",\n    @Json(name = "features") val features: List<String> = emptyList(),',
    "Prime features JSON model and consistent shipping default")
patch(VM,
    '                        packagingFeature = config.primePackagingFeature,\n                        themeFeature = config.primeThemeFeature,\n                        buttonText = config.primeButtonText,',
    '                        packagingFeature = config.primePackagingFeature,\n                        themeFeature = config.primeThemeFeature,\n                        features = config.primeExtraFeatures.map { it.trim() }.filter { it.isNotEmpty() }.take(12),\n                        buttonText = config.primeButtonText,',
    "persist Prime feature list")
patch(VM,
    '                            primeThemeFeature = cfgObj?.prime?.themeFeature ?: currentConfig.primeThemeFeature,\n                            primeButtonText = cfgObj?.prime?.buttonText ?: currentConfig.primeButtonText,',
    '                            primeThemeFeature = cfgObj?.prime?.themeFeature ?: currentConfig.primeThemeFeature,\n                            primeExtraFeatures = cfgObj?.prime?.features ?: currentConfig.primeExtraFeatures,\n                            primeButtonText = cfgObj?.prime?.buttonText ?: currentConfig.primeButtonText,',
    "restore Prime feature list from Supabase")
patch(EDITOR,
'''        OutlinedTextField(
            value = config.primeThemeFeature,
            onValueChange = { onUpdate(config.copy(primeThemeFeature = it)) },
            label = { Text("ميزة الهوية والمظهر للأعضاء") },
            modifier = Modifier.fillMaxWidth()
        )

        OutlinedTextField(
            value = config.primeButtonText,''',
'''        OutlinedTextField(
            value = config.primeThemeFeature,
            onValueChange = { onUpdate(config.copy(primeThemeFeature = it)) },
            label = { Text("ميزة الهوية والمظهر للأعضاء (اتركيها فارغة لإيقافها)") },
            modifier = Modifier.fillMaxWidth()
        )

        OutlinedTextField(
            value = config.primeExtraFeatures.joinToString("\\n"),
            onValueChange = { raw ->
                onUpdate(config.copy(primeExtraFeatures = raw.lines().map { it.trim() }.filter { it.isNotEmpty() }.take(12)))
            },
            label = { Text("مميزات إضافية (كل ميزة في سطر مستقل)") },
            supportingText = { Text("يمكنك إضافة أو حذف المميزات بتعديل السطور. الحد الأقصى 12 ميزة.") },
            modifier = Modifier.fillMaxWidth(),
            minLines = 3
        )

        OutlinedTextField(
            value = config.primeButtonText,''',
    "Prime add/remove feature editor")
patch(EDITOR,
    'onValueChange = { onUpdate(config.copy(primeFreeShippingOrdersCount = it.toIntOrNull() ?: 4)) },',
    'onValueChange = { onUpdate(config.copy(primeFreeShippingOrdersCount = it.toIntOrNull() ?: 6)) },',
    "Prime shipping editor default")
patch(VM,
'''        viewModelScope.launch {
            _websiteSaveState.value = "saving"
            try {
                // 1. Store settings''',
'''        viewModelScope.launch {
            val validPrime = config.primePrice.isFinite() && config.primePrice > 0.0 &&
                config.primeDurationDays in 1..3650 &&
                config.primeDiscountPercent.isFinite() && config.primeDiscountPercent in 0.0..100.0 &&
                config.primeFreeShippingOrdersCount in 0..100 &&
                config.primeExtraFeatures.size <= 12 &&
                config.primeExtraFeatures.all { it.isNotBlank() && it.length <= 100 }
            if (!validPrime) {
                _websiteSaveState.value = "error"
                notifyUser("راجعي إعدادات Prime: السعر أكبر من صفر، المدة 1–3650 يومًا، الخصم 0–100%، والشحن 0–100.")
                return@launch
            }
            _websiteSaveState.value = "saving"
            try {
                // 1. Store settings''',
    "Prime settings validation before saving")
patch(MOCKUP,
'''                        Text(config.primeName, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Text(config.primeDescription, color = Color.White.copy(alpha = .8f), fontSize = 10.sp)
                    }''',
'''                        Text(config.primeName, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Text(config.primeDescription, color = Color.White.copy(alpha = .8f), fontSize = 10.sp)
                        config.primeExtraFeatures.forEach { feature ->
                            Text("• $feature", color = Color.White.copy(alpha = .9f), fontSize = 9.sp)
                        }
                    }''',
    "Prime feature list in phone preview")
vm_text = (ROOT / VM).read_text(encoding="utf-8")
if "isStoreOpen = config.isStoreOpen" not in vm_text or "isStoreOpen = cfgObj?.global?.isStoreOpen" not in vm_text:
    raise SystemExit("Store open/close persistence was altered or is missing")
for relative, markers in {
    MODEL: ("primeExtraFeatures: List<String>",),
    JSON: ('@Json(name = "features") val features: List<String>',),
    VM: ("features = config.primeExtraFeatures", "primeExtraFeatures = cfgObj?.prime?.features", "config.primePrice.isFinite()"),
    EDITOR: ("مميزات إضافية (كل ميزة في سطر مستقل)", "primeExtraFeatures = raw.lines()"),
    MOCKUP: ("config.primeExtraFeatures.forEach",)
}.items():
    source = (ROOT / relative).read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in source]
    if missing: raise SystemExit(f"Prime settings verification failed in {relative}: {missing}")
print("PASS: Prime controls and feature list are wired; store open/close remains intact.")


patch(
    MODEL,
    '    val primeButtonText: String = "اشتركي الآن",\n    val primeIsVisible: Boolean = true,',
    '    val primeButtonText: String = "اشتركي الآن",\n    val primeEnabled: Boolean = true,\n    val primeIsVisible: Boolean = true,',
    "Prime purchase enable switch model"
)
patch(
    JSON,
    '    @Json(name = "buttonText") val buttonText: String = "اشتركي الآن",\n    @Json(name = "isVisible") val isVisible: Boolean = true',
    '    @Json(name = "buttonText") val buttonText: String = "اشتركي الآن",\n    @Json(name = "enabled") val enabled: Boolean = true,\n    @Json(name = "isVisible") val isVisible: Boolean = true',
    "Prime purchase enable JSON model"
)
patch(
    VM,
    '                        buttonText = config.primeButtonText,\n                        isVisible = config.primeIsVisible',
    '                        buttonText = config.primeButtonText,\n                        enabled = config.primeEnabled,\n                        isVisible = config.primeIsVisible',
    "persist Prime purchase enabled state"
)
patch(
    VM,
    '                            primeButtonText = cfgObj?.prime?.buttonText ?: currentConfig.primeButtonText,\n                            primeIsVisible = cfgObj?.prime?.isVisible ?: currentConfig.primeIsVisible,',
    '                            primeButtonText = cfgObj?.prime?.buttonText ?: currentConfig.primeButtonText,\n                            primeEnabled = cfgObj?.prime?.enabled ?: currentConfig.primeEnabled,\n                            primeIsVisible = cfgObj?.prime?.isVisible ?: currentConfig.primeIsVisible,',
    "restore Prime purchase enabled state"
)
patch(
    EDITOR,
    '''    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("عرض بنر اشتراك برايم في الصفحة الرئيسية", fontWeight = FontWeight.SemiBold)''',
    '''    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(Modifier.weight(1f)) {
                Text("تفعيل اشتراكات Elory Prime", fontWeight = FontWeight.SemiBold)
                Text("إيقاف البيع لا يلغي اشتراكات العملاء الحالية.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(
                checked = config.primeEnabled,
                onCheckedChange = { onUpdate(config.copy(primeEnabled = it)) }
            )
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text("عرض بنر اشتراك برايم في الصفحة الرئيسية", fontWeight = FontWeight.SemiBold)''',
    "Prime purchase enable switch UI"
)


ORDER_MODEL = "app/src/main/java/com/pinky/dashboard/domain/model/Order.kt"
ORDER_DTO = "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
ENTITIES = "app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt"
DATABASE = "app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt"
REPOSITORY = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
ORDER_DETAIL = "app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt"

patch(
    ORDER_MODEL,
    '    val primeRequested: Boolean = false,\n    val profit: Double = 0.0,',
    '    val primeRequested: Boolean = false,\n    val primePackaging: Boolean = false,\n    val profit: Double = 0.0,',
    "Prime packaging domain model"
)
patch(
    ORDER_DTO,
    '    @Json(name = "prime") val prime: Boolean? = null,\n    @Json(name = "profit") val profit: Double? = null,',
    '    @Json(name = "prime") val prime: Boolean? = null,\n    @Json(name = "prime_packaging") val primePackaging: Boolean? = null,\n    @Json(name = "profit") val profit: Double? = null,',
    "Prime packaging API DTO"
)
patch(
    ENTITIES,
    '    val primeRequested: Boolean = false,\n    val prime: Boolean = false,\n    val profit: Double = 0.0,',
    '    val primeRequested: Boolean = false,\n    val prime: Boolean = false,\n    @ColumnInfo(defaultValue = "0") val primePackaging: Boolean = false,\n    val profit: Double = 0.0,',
    "Prime packaging Room entity"
)
patch(DATABASE, '    version = 6,', '    version = 7,', "Room database version for Prime packaging")
patch(
    DATABASE,
    '''        private val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN customerOrderCode TEXT NOT NULL DEFAULT ''")
            }
        }
''',
    '''        private val MIGRATION_5_6 = object : Migration(5, 6) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN customerOrderCode TEXT NOT NULL DEFAULT ''")
            }
        }

        private val MIGRATION_6_7 = object : Migration(6, 7) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE orders ADD COLUMN primePackaging INTEGER NOT NULL DEFAULT 0")
            }
        }
''',
    "Room migration for Prime packaging"
)
patch(
    DATABASE,
    '.addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6)',
    '.addMigrations(MIGRATION_3_4, MIGRATION_4_5, MIGRATION_5_6, MIGRATION_6_7)',
    "Register Prime packaging Room migration"
)
patch(
    REPOSITORY,
    '                    primeRequested = entity.primeRequested,\n                    profit = entity.profit,',
    '                    primeRequested = entity.primeRequested,\n                    primePackaging = entity.primePackaging,\n                    profit = entity.profit,',
    "Map Prime packaging from cached order list"
)
patch(
    REPOSITORY,
    '                    primeRequested = entity.primeRequested,\n            profit = entity.profit,',
    '                    primeRequested = entity.primeRequested,\n                    primePackaging = entity.primePackaging,\n            profit = entity.profit,',
    "Map Prime packaging from cached order detail"
)
patch(
    REPOSITORY,
    '                        primeRequested = dto.primeRequested ?: false,\n                        profit = dto.profit ?: 0.0,',
    '                        primeRequested = dto.primeRequested ?: false,\n                        primePackaging = dto.primePackaging ?: false,\n                        profit = dto.profit ?: 0.0,',
    "Map Prime packaging from Supabase orders"
)
patch(
    REPOSITORY,
    '                notes = order.notes,\n                isSynced = true\n            )',
    '                notes = order.notes,\n                isSynced = true,\n                primePackaging = order.primePackaging\n            )',
    "Persist Prime packaging in local order cache"
)
patch(
    ORDER_DETAIL,
    '''                                    if (order.couponFreeShipping) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                imageVector = Icons.Outlined.LocalShipping,
                                                contentDescription = null,
                                                tint = Color(0xFF10B981),
                                                modifier = Modifier.size(16.dp)
                                            )
                                            Text(
                                                text = "الشحن مجاني بالكامل بفضل هذا الكوبون 🎁",
                                                style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.SemiBold),
                                                color = Color(0xFF047857)
                                            )
                                        }
                                    }
''',
    '''                                    if (order.couponFreeShipping) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                imageVector = Icons.Outlined.LocalShipping,
                                                contentDescription = null,
                                                tint = Color(0xFF10B981),
                                                modifier = Modifier.size(16.dp)
                                            )
                                            Text(
                                                text = "الشحن مجاني بالكامل بفضل هذا الكوبون 🎁",
                                                style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.SemiBold),
                                                color = Color(0xFF047857)
                                            )
                                        }
                                    }

                                    if (order.primePackaging) {
                                        Row(
                                            modifier = Modifier.fillMaxWidth(),
                                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                                            verticalAlignment = Alignment.CenterVertically
                                        ) {
                                            Icon(
                                                imageVector = Icons.Outlined.CardGiftcard,
                                                contentDescription = null,
                                                tint = Color(0xFFB7791F),
                                                modifier = Modifier.size(16.dp)
                                            )
                                            Text(
                                                text = "هذا الطلب يشمل التغليف المميز من Elory Prime 🎁",
                                                style = MaterialTheme.typography.bodySmall.copy(fontWeight = FontWeight.SemiBold),
                                                color = Color(0xFF92400E)
                                            )
                                        }
                                    }
''',
    "Show Prime packaging benefit in order detail"
)
for relative, markers in {
    ORDER_MODEL: ("primePackaging: Boolean",),
    ORDER_DTO: ('@Json(name = "prime_packaging")',),
    ENTITIES: ("primePackaging: Boolean",),
    DATABASE: ("version = 7", "MIGRATION_6_7", "primePackaging INTEGER"),
    REPOSITORY: ("primePackaging = dto.primePackaging ?: false", "primePackaging = entity.primePackaging", "primePackaging = order.primePackaging"),
    ORDER_DETAIL: ("هذا الطلب يشمل التغليف المميز من Elory Prime",)
}.items():
    source = (ROOT / relative).read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in source]
    if missing: raise SystemExit(f"Prime packaging verification failed in {relative}: {missing}")
print("PASS: Prime packaging is persisted on eligible orders and visible to staff.")
