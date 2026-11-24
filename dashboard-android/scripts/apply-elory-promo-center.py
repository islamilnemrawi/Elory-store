from pathlib import Path
import os
ROOT=Path(os.environ["PROJECT_DIR"]).resolve()
def F(p): return ROOT/p
def R(p,a,b,label):
    x=F(p); s=x.read_text(encoding="utf-8"); n=s.count(a)
    if n==0 and b in s: print("Already "+label); return
    if n!=1: raise SystemExit("Anchor count for "+label+": "+str(n))
    x.write_text(s.replace(a,b,1),encoding="utf-8"); print("PASS "+label)
def G(p,start,end,new,label):
    x=F(p); s=x.read_text(encoding="utf-8"); a=s.find(start)
    if a<0:
        if new.strip() in s: print("Already "+label); return
        raise SystemExit("Missing start "+label)
    b=s.find(end,a+len(start))
    if b<0: raise SystemExit("Missing end "+label)
    x.write_text(s[:a]+new+"\n\n"+s[b:],encoding="utf-8"); print("PASS "+label)

MODEL="app/src/main/java/com/pinky/dashboard/domain/model/StoreModels.kt"
JSON="app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt"
REMOTE="app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
VM="app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
APP="app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt"
OFFERS="app/src/main/java/com/pinky/dashboard/ui/screens/offers/OffersScreen.kt"
WEBSITE="app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"

R(MODEL,'data class WebsiteConfig(\n    val storeName: String = "Elory Store",','data class WebsiteConfig(\n    val isStoreOpen: Boolean = true,\n    val storeName: String = "Elory Store",',"website status model")
R(JSON,'    @Json(name = "fontFamily") val fontFamily: String = ""\n)','    @Json(name = "fontFamily") val fontFamily: String = "",\n    @Json(name = "isStoreOpen") val isStoreOpen: Boolean = true\n)',"website status JSON")
R(VM,'                        announcementColor = config.announcementBgColor,\n                        fontFamily = config.fontFamily','                        announcementColor = config.announcementBgColor,\n                        fontFamily = config.fontFamily,\n                        isStoreOpen = config.isStoreOpen',"save store status")
R(VM,'                            fontFamily = customizations.fontFamily,\n                            sections = cfgObj?.sections?.map {','                            fontFamily = customizations.fontFamily,\n                            isStoreOpen = cfgObj?.global?.isStoreOpen ?: currentConfig.isStoreOpen,\n                            sections = cfgObj?.sections?.map {',"load store status")

R(MODEL,'    val isFirstOrderOnly: Boolean = false, // خيار خاص "أول طلب فقط"\n    val startDate: Long = System.currentTimeMillis(),','    val isFirstOrderOnly: Boolean = false,\n    val perCustomerLimit: Int? = 1,\n    val audienceMode: String = "all_customers",\n    val startDate: Long = System.currentTimeMillis(),',"coupon limits model")
R(REMOTE,'    @Json(name = "used_count") val usedCount: Int? = 0,\n    @Json(name = "starts_at") val startsAt: String? = null,','    @Json(name = "used_count") val usedCount: Int? = 0,\n    @Json(name = "first_order_only") val firstOrderOnly: Boolean? = false,\n    @Json(name = "per_customer_limit") val perCustomerLimit: Int? = 1,\n    @Json(name = "audience_mode") val audienceMode: String? = "all_customers",\n    @Json(name = "starts_at") val startsAt: String? = null,',"coupon DTO")
R(VM,'                    discountType = coupon.discountType.name,','                    discountType = if (coupon.discountType == DiscountType.PERCENTAGE) "percent" else "fixed",',"map coupon type")
R(VM,'                            discountType = try { DiscountType.valueOf(dto.discountType) } catch (e: Exception) { DiscountType.PERCENTAGE },','                            discountType = if (dto.discountType.equals("fixed", true)) DiscountType.FIXED else DiscountType.PERCENTAGE,',"read percent/fixed coupon type")
R(VM,'                    usedCount = coupon.usageCount,\n                    startsAt = coupon.startDate.toSupabaseIsoTimestamp(),','                    usedCount = coupon.usageCount,\n                    firstOrderOnly = coupon.isFirstOrderOnly,\n                    perCustomerLimit = coupon.perCustomerLimit,\n                    audienceMode = coupon.audienceMode,\n                    startsAt = coupon.startDate.toSupabaseIsoTimestamp(),',"save coupon controls")
R(VM,'                            isFirstOrderOnly = false,\n                            startDate = dto.startsAt.toEpochMillisOrNull()','                            isFirstOrderOnly = dto.firstOrderOnly ?: false,\n                            perCustomerLimit = dto.perCustomerLimit,\n                            audienceMode = dto.audienceMode ?: "all_customers",\n                            startDate = dto.startsAt.toEpochMillisOrNull()',"load coupon controls")

G(VM,'    // Coupon management: update local state only after Supabase confirms the write.\n    fun saveCoupon(coupon: Coupon) {','\n    fun deleteCoupon(couponId: String) {',r'''    suspend fun saveCoupon(coupon: Coupon): Result<Unit> =
        kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
            try {
                val dto = SupabaseCouponDto(
                    id = coupon.id,
                    code = coupon.code.trim().uppercase(),
                    discountType = if (coupon.discountType == DiscountType.PERCENTAGE) "percent" else "fixed",
                    discountValue = coupon.discountValue,
                    minOrder = coupon.minOrderAmount,
                    maxDiscount = coupon.maxDiscountAmount,
                    freeShipping = coupon.isFreeShipping,
                    usageLimit = coupon.usageLimit,
                    usedCount = coupon.usageCount,
                    firstOrderOnly = coupon.isFirstOrderOnly,
                    perCustomerLimit = coupon.perCustomerLimit,
                    audienceMode = coupon.audienceMode,
                    startsAt = coupon.startDate.toSupabaseIsoTimestamp(),
                    expiresAt = coupon.endDate.toSupabaseIsoTimestamp(),
                    active = coupon.isActive
                )
                val written = SupabaseClient.service.upsertCoupon(dto)
                if (!written.isSuccessful) {
                    val detail = written.errorBody()?.string().orEmpty().take(400)
                    return@withContext Result.failure(IllegalStateException("فشل حفظ الكوبون. $detail"))
                }
                val refreshed = SupabaseClient.service.getCoupons()
                if (!refreshed.isSuccessful) {
                    val detail = refreshed.errorBody()?.string().orEmpty().take(300)
                    return@withContext Result.failure(IllegalStateException("تعذر تأكيد ظهور الكوبون. $detail"))
                }
                _coupons.value = (refreshed.body() ?: emptyList()).map { item ->
                    Coupon(
                        id = item.id,
                        code = item.code,
                        discountType = if (item.discountType.equals("fixed", true)) DiscountType.FIXED else DiscountType.PERCENTAGE,
                        discountValue = item.discountValue,
                        minOrderAmount = item.minOrder ?: 0.0,
                        maxDiscountAmount = item.maxDiscount,
                        isFreeShipping = item.freeShipping ?: false,
                        usageLimit = item.usageLimit,
                        usageCount = item.usedCount ?: 0,
                        isFirstOrderOnly = item.firstOrderOnly ?: false,
                        perCustomerLimit = item.perCustomerLimit,
                        audienceMode = item.audienceMode ?: "all_customers",
                        startDate = item.startsAt.toEpochMillisOrNull() ?: System.currentTimeMillis(),
                        endDate = item.expiresAt.toEpochMillisOrNull() ?: (System.currentTimeMillis() + 30L * 24 * 60 * 60 * 1000),
                        isActive = item.active ?: true
                    )
                }
                Result.success(Unit)
            } catch (error: Exception) {
                android.util.Log.e("EloryCoupon", "Coupon save failed", error)
                Result.failure(error)
            }
        }
''',"await coupon write and refresh")

p=F(OFFERS); s=p.read_text(encoding="utf-8")
for imp in ['import com.pinky.dashboard.ui.screens.website.HeroBannersForm\n','import kotlinx.coroutines.launch\n','import java.util.UUID\n','import androidx.compose.foundation.BorderStroke\n','import androidx.compose.foundation.rememberScrollState\n','import androidx.compose.foundation.verticalScroll\n']:
    if imp.strip() not in s:
        s=s.replace('import com.pinky.dashboard.domain.model.*\n','import com.pinky.dashboard.domain.model.*\n'+imp,1)
old='''    onSaveCoupon: (Coupon) -> Unit,
    onDeleteCoupon: (String) -> Unit,
    onToggleCouponActive: (String, Boolean) -> Unit,
    modifier: Modifier = Modifier
) {'''
new='''    onSaveCoupon: suspend (Coupon) -> Result<Unit>,
    onDeleteCoupon: (String) -> Unit,
    onToggleCouponActive: (String, Boolean) -> Unit,
    websiteConfig: WebsiteConfig,
    onSaveWebsiteConfig: (WebsiteConfig) -> Unit,
    websiteSaveState: String = "idle",
    modifier: Modifier = Modifier
) {'''
if s.count(old)!=1: raise SystemExit("OffersScreen params mismatch")
s=s.replace(old,new,1)
anchor='    var couponToDelete by remember { mutableStateOf<Coupon?>(null) }\n'
if s.count(anchor)!=1: raise SystemExit("OffersScreen state mismatch")
s=s.replace(anchor,anchor+'''    var localHeroConfig by remember { mutableStateOf(websiteConfig) }
    var heroDirty by remember { mutableStateOf(false) }
    LaunchedEffect(websiteConfig) { localHeroConfig = websiteConfig; heroDirty = false }
    LaunchedEffect(websiteSaveState) { if (websiteSaveState == "success") heroDirty = false }
''',1)
a=s.find('        floatingActionButton = {'); b=s.find('        modifier = modifier.testTag("offers_screen")',a)
if a<0 or b<0: raise SystemExit("offers FAB boundary missing")
s=s[:a]+'''        floatingActionButton = {
            if (selectedTab == 1) ExtendedFloatingActionButton(
                onClick = { editingCoupon = null; showCouponDialog = true },
                containerColor = PinkPrimary,
                contentColor = Color(0xFF381528),
                icon = { Icon(Icons.Outlined.Add, contentDescription = null) },
                text = { Text("إنشاء كوبون جديد", fontWeight = FontWeight.Bold) },
                modifier = Modifier.testTag("add_coupon_fab")
            )
        },
'''+s[b:]
# Build this exact anchor without evaluating Kotlin's template placeholder.
oldTab='text = { Text("العروض والبنرات (' + chr(36) + '{offers.size})", fontWeight = FontWeight.Bold) },'
s=s.replace(oldTab,'text = { Text("البنرات والهيرو", fontWeight = FontWeight.Bold) },',1)
a=s.find('            if (selectedTab == 0) {\n                // Offers & Banners Tab'); b=s.find('            } else {\n                // Coupons Tab',a)
if a<0 or b<0: raise SystemExit("offers tab block boundary missing")
branch='''            if (selectedTab == 0) {
                Column(Modifier.fillMaxSize().padding(horizontal = 14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    val heroImageReady = localHeroConfig.heroSlides.any {
                        it.isActive && (it.mediaUrl.isNotBlank() || it.imageUrl.isNotBlank())
                    }
                    Text("مركز البنرات والهيرو", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = PinkPrimary)
                    Text("ارفع تصميم الصورة كاملًا، ثم أضف زرًا فوقها وحدد مكانه ورابطه. الحفظ يحدّث نفس إعدادات الهيرو التي يقرأها المتجر.",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                    ) {
                        Row(
                            Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text("إظهار قسم الهيرو على الموقع", fontWeight = FontWeight.SemiBold)
                                Text("يمكن إخفاء الهيرو بالكامل مع الاحتفاظ بالشرائح والصور.", style = MaterialTheme.typography.bodySmall)
                            }
                            Switch(
                                checked = localHeroConfig.showHeroBanner,
                                onCheckedChange = { show ->
                                    localHeroConfig = localHeroConfig.copy(showHeroBanner = show)
                                    heroDirty = true
                                }
                            )
                        }
                    }
                    Box(Modifier.weight(1f).fillMaxWidth()) {
                        HeroBannersForm(config = localHeroConfig, onUpdate = {
                            localHeroConfig = it
                            heroDirty = true
                        })
                    }
                    if (localHeroConfig.showHeroBanner && !heroImageReady) {
                        Text("لا يمكن نشر الهيرو وهو ظاهر بدون صورة نشطة. ارفع صورة لإحدى الشرائح أو أوقف إظهار الهيرو.", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                    Button(
                        onClick = { onSaveWebsiteConfig(localHeroConfig) },
                        enabled = heroDirty && websiteSaveState != "saving" && (!localHeroConfig.showHeroBanner || heroImageReady),
                        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
                    ) {
                        if (websiteSaveState == "saving") {
                            CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp)); Text("جارٍ حفظ شرائح الهيرو...")
                        } else {
                            Icon(Icons.Outlined.Save, contentDescription = null)
                            Spacer(Modifier.width(8.dp)); Text("حفظ ونشر البنرات", fontWeight = FontWeight.Bold)
                        }
                    }
                    when (websiteSaveState) {
                        "success" -> Text("تم حفظ البنرات في إعدادات الهيرو.", color = Color(0xFF16834A))
                        "error" -> Text("فشل حفظ البنرات. راجع الاتصال والصلاحيات ثم أعد المحاولة.", color = MaterialTheme.colorScheme.error)
                    }
                }
'''
s=s[:a]+branch+s[b:]
oldCb='''            onSave = {
                onSaveCoupon(it)
                showCouponDialog = false
            }'''
newCb='''            onSave = { saved -> onSaveCoupon(saved) },
            onSaved = { showCouponDialog = false }'''
if s.count(oldCb)!=1: raise SystemExit("coupon dialog callback missing")
s=s.replace(oldCb,newCb,1)

a=s.find('@Composable\nfun CouponEditDialog(')
if a<0: raise SystemExit("CouponEditDialog missing")
s=s[:a]+r'''@Composable
fun CouponEditDialog(
    coupon: Coupon?,
    onDismiss: () -> Unit,
    onSave: suspend (Coupon) -> Result<Unit>,
    onSaved: () -> Unit
) {
    var code by remember(coupon?.id) { mutableStateOf(coupon?.code ?: "") }
    var discountType by remember(coupon?.id) { mutableStateOf(coupon?.discountType ?: DiscountType.PERCENTAGE) }
    var value by remember(coupon?.id) { mutableStateOf(coupon?.discountValue?.toString() ?: "10") }
    var minimum by remember(coupon?.id) { mutableStateOf(coupon?.minOrderAmount?.toString() ?: "0") }
    var maximum by remember(coupon?.id) { mutableStateOf(coupon?.maxDiscountAmount?.toString() ?: "") }
    var totalLimit by remember(coupon?.id) { mutableStateOf(coupon?.usageLimit?.toString() ?: "") }
    var customerLimit by remember(coupon?.id) { mutableStateOf(coupon?.perCustomerLimit?.toString() ?: "1") }
    var audience by remember(coupon?.id) { mutableStateOf(coupon?.audienceMode ?: "all_customers") }
    var firstOrder by remember(coupon?.id) { mutableStateOf(coupon?.isFirstOrderOnly ?: false) }
    var freeShipping by remember(coupon?.id) { mutableStateOf(coupon?.isFreeShipping ?: false) }
    var active by remember(coupon?.id) { mutableStateOf(coupon?.isActive ?: true) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Dialog(onDismissRequest = { if (!saving) onDismiss() }) {
        Card(shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth(0.97f)) {
            Column(
                modifier = Modifier.padding(18.dp).heightIn(max = 680.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(if (coupon == null) "إنشاء كوبون احترافي" else "تعديل الكوبون",
                    style = MaterialTheme.typography.titleLarge.copy(fontWeight = FontWeight.Bold), color = PinkPrimary)
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it.uppercase().filter { ch -> ch.isLetterOrDigit() || ch == '_' || ch == '-' }.take(32) },
                    label = { Text("كود الخصم") }, placeholder = { Text("ELORY20") },
                    modifier = Modifier.fillMaxWidth().testTag("coupon_code_input"), singleLine = true
                )
                TextButton(
                    onClick = { code = "ELORY-" + UUID.randomUUID().toString().replace("-", "").take(8).uppercase() },
                    modifier = Modifier.align(Alignment.End)
                ) { Text("توليد كود عشوائي") }

                Text("نوع الخصم", fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(discountType == DiscountType.PERCENTAGE, { discountType = DiscountType.PERCENTAGE }, label = { Text("نسبة %") })
                    FilterChip(discountType == DiscountType.FIXED, { discountType = DiscountType.FIXED }, label = { Text("مبلغ ثابت ج.م") })
                }
                OutlinedTextField(value, { value = it.filter { ch -> ch.isDigit() || ch == '.' } },
                    label = { Text("قيمة الخصم") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(minimum, { minimum = it.filter { ch -> ch.isDigit() || ch == '.' } },
                    label = { Text("الحد الأدنى للطلب") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(maximum, { maximum = it.filter { ch -> ch.isDigit() || ch == '.' } },
                    label = { Text("أقصى مبلغ للخصم (اختياري)") }, placeholder = { Text("فارغ = بلا سقف") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth(), singleLine = true)

                Divider()
                Text("نوع الجمهور", fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(audience == "all_customers", { audience = "all_customers" }, label = { Text("كود مشترك") })
                    FilterChip(audience == "single_customer", { audience = "single_customer" }, label = { Text("عميل واحد فقط") })
                }
                Text(
                    if (audience == "single_customer") "أول عميل يستخدم الكود بنجاح يرتبط به، ولن يقبله المتجر لعميل آخر."
                    else "يمكن لعدة عملاء استخدام الكود نفسه وفق الحدود المحددة.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                OutlinedTextField(totalLimit, { totalLimit = it.filter(Char::isDigit) },
                    label = { Text("الحد الإجمالي للاستخدام") }, placeholder = { Text("1 = مرة واحدة إجمالًا، فارغ = بلا حد") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth(), singleLine = true)
                OutlinedTextField(customerLimit, { customerLimit = it.filter(Char::isDigit) },
                    label = { Text("مرات الاستخدام لكل رقم هاتف") }, placeholder = { Text("1 = مرة لكل عميل، فارغ = بلا حد") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth(), singleLine = true)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("أول طلب فقط", modifier = Modifier.weight(1f)); Switch(firstOrder, { firstOrder = it })
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("شحن مجاني مع الخصم", modifier = Modifier.weight(1f)); Switch(freeShipping, { freeShipping = it })
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("الكوبون مفعّل", modifier = Modifier.weight(1f)); Switch(active, { active = it })
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(
                        onClick = {
                            val normalized = code.trim().uppercase()
                            val parsedValue = value.toDoubleOrNull()
                            val min = minimum.toDoubleOrNull() ?: 0.0
                            val max = maximum.toDoubleOrNull()
                            val maxUses = totalLimit.toIntOrNull()
                            val perCustomer = customerLimit.toIntOrNull()
                            val invalid = when {
                                normalized.length !in 3..32 -> "اكتب كودًا من 3 إلى 32 حرفًا."
                                parsedValue == null || parsedValue < 0 -> "قيمة الخصم غير صحيحة."
                                discountType == DiscountType.PERCENTAGE && parsedValue > 100 -> "النسبة لا يمكن أن تتجاوز 100%."
                                parsedValue == 0.0 && !freeShipping -> "أضف خصمًا أو فعّل الشحن المجاني."
                                min < 0 || (max != null && max <= 0) -> "تحقق من الحد الأدنى وأقصى الخصم."
                                totalLimit.isNotBlank() && (maxUses == null || maxUses < 1) -> "الحد الإجمالي يجب أن يكون 1 أو أكثر."
                                customerLimit.isNotBlank() && (perCustomer == null || perCustomer < 1) -> "حد العميل يجب أن يكون 1 أو أكثر."
                                else -> null
                            }
                            if (invalid != null) { error = invalid; return@Button }
                            val saved = Coupon(
                                id = coupon?.id ?: UUID.randomUUID().toString(),
                                code = normalized,
                                discountType = discountType,
                                discountValue = parsedValue ?: 0.0,
                                minOrderAmount = min,
                                maxDiscountAmount = max,
                                isFreeShipping = freeShipping,
                                usageLimit = maxUses,
                                usageCount = coupon?.usageCount ?: 0,
                                isFirstOrderOnly = firstOrder,
                                perCustomerLimit = perCustomer,
                                audienceMode = audience,
                                startDate = coupon?.startDate ?: System.currentTimeMillis(),
                                endDate = coupon?.endDate ?: (System.currentTimeMillis() + 30L * 24 * 60 * 60 * 1000),
                                isActive = active
                            )
                            saving = true; error = null
                            scope.launch {
                                val savedResult = onSave(saved)
                                saving = false
                                savedResult.onSuccess { onSaved() }
                                savedResult.onFailure { error = it.message ?: "تعذر حفظ الكوبون." }
                            }
                        },
                        enabled = !saving,
                        modifier = Modifier.weight(1f).testTag("save_coupon_btn"),
                        colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
                    ) {
                        if (saving) CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                        else Text("حفظ الكوبون", fontWeight = FontWeight.Bold)
                    }
                    OutlinedButton(onClick = onDismiss, enabled = !saving) { Text("إلغاء") }
                }
            }
        }
    }
}
'''
p.write_text(s,encoding="utf-8")
print("PASS hero center and coupon editor")

app=F(APP); a=app.read_text(encoding="utf-8")
oldCall='''                                OffersScreen(
                                    offers = offers,
                                    coupons = coupons,
                                    categories = categories,
                                    onSaveOffer = { viewModel.saveOffer(it) },
                                    onDeleteOffer = { viewModel.deleteOffer(it) },
                                    onSaveCoupon = { viewModel.saveCoupon(it) },
                                    onDeleteCoupon = { viewModel.deleteCoupon(it) },
                                    onToggleCouponActive = { id, active -> viewModel.toggleCouponActive(id, active) }
                                )'''
newCall='''                                OffersScreen(
                                    offers = offers,
                                    coupons = coupons,
                                    categories = categories,
                                    onSaveOffer = { viewModel.saveOffer(it) },
                                    onDeleteOffer = { viewModel.deleteOffer(it) },
                                    onSaveCoupon = { viewModel.saveCoupon(it) },
                                    onDeleteCoupon = { viewModel.deleteCoupon(it) },
                                    onToggleCouponActive = { id, active -> viewModel.toggleCouponActive(id, active) },
                                    websiteConfig = websiteConfig,
                                    onSaveWebsiteConfig = { viewModel.updateWebsiteConfig(it) },
                                    websiteSaveState = websiteSaveState
                                )'''
if a.count(oldCall)!=1: raise SystemExit("PinkyApp wiring anchor missing")
app.write_text(a.replace(oldCall,newCall,1),encoding="utf-8")
print("PASS hero manager app wiring")


R(WEBSITE,
  '                    // Card 1: الشريط العلوي',
  '''                    item {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            border = CardDefaults.outlinedCardBorder(),
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
                        ) {
                            Row(
                                Modifier.fillMaxWidth().padding(18.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                Icon(
                                    if (config.isStoreOpen) Icons.Outlined.Storefront else Icons.Outlined.Lock,
                                    contentDescription = null,
                                    tint = if (config.isStoreOpen) Color(0xFF16834A) else MaterialTheme.colorScheme.error,
                                    modifier = Modifier.size(30.dp)
                                )
                                Column(Modifier.weight(1f)) {
                                    Text(if (config.isStoreOpen) "المتجر مفتوح للزوار" else "المتجر مغلق مؤقتًا", fontWeight = FontWeight.Bold)
                                    Text(
                                        if (config.isStoreOpen) "العملاء يستطيعون تصفح المنتجات وإرسال الطلبات."
                                        else "سيظهر للزوار إشعار بأن المتجر مغلق مؤقتًا.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                Switch(checked = config.isStoreOpen, onCheckedChange = { config = config.copy(isStoreOpen = it) })
                            }
                        }
                    }

                    // Card 1: الشريط العلوي''',
  "preserve store availability toggle and all CMS editor sections")


checks=[
 (MODEL,'val isStoreOpen: Boolean = true'),
 (JSON,'@Json(name = "isStoreOpen") val isStoreOpen: Boolean = true'),
 (REMOTE,'@Json(name = "per_customer_limit")'),
 (REMOTE,'@Json(name = "first_order_only")'),
 (VM,'discountType = if (coupon.discountType == DiscountType.PERCENTAGE) "percent" else "fixed"'),
 (OFFERS,'UUID.randomUUID().toString()'),
 (OFFERS,'onSave: suspend (Coupon) -> Result<Unit>'),
 (WEBSITE,'Switch(checked = config.isStoreOpen')
]
for rel,m in checks:
    if m not in F(rel).read_text(encoding="utf-8"): raise SystemExit("Missing verification "+m)
    print("PASS "+m)
