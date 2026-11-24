import os
import re
from pathlib import Path
root = Path(os.environ["PROJECT_DIR"])

def replace(path, old, new, count=1):
    p=root/path
    s=p.read_text(encoding='utf-8')
    n=s.count(old)
    if n < count:
        raise SystemExit(f'Expected {count} occurrence(s) in {path}, found {n}: {old[:100]!r}')
    s=s.replace(old,new,count)
    p.write_text(s,encoding='utf-8')

# Structured JSON models: sections, dynamic slides, and custom page sections.
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''    @Json(name = "navigation") val navigation: List<NavigationConfig>? = null,
    @Json(name = "hero") val hero: HeroConfig? = null,''',
'''    @Json(name = "navigation") val navigation: List<NavigationConfig>? = null,
    @Json(name = "sections") val sections: List<SiteSectionConfig>? = null,
    @Json(name = "hero") val hero: HeroConfig? = null,''')
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''    @Json(name = "customSections") val customSections: List<String>? = null
)''',
'''    @Json(name = "customSections") val customSections: List<CustomSiteSectionConfig>? = null
)

@JsonClass(generateAdapter = true)
data class SiteSectionConfig(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "isVisible") val isVisible: Boolean = true,
    @Json(name = "sortOrder") val sortOrder: Int = 0
)

@JsonClass(generateAdapter = true)
data class CustomSiteSectionConfig(
    @Json(name = "id") val id: String,
    @Json(name = "title") val title: String,
    @Json(name = "text") val text: String = "",
    @Json(name = "imageUrl") val imageUrl: String = "",
    @Json(name = "buttonText") val buttonText: String = "",
    @Json(name = "buttonUrl") val buttonUrl: String = "",
    @Json(name = "backgroundColor") val backgroundColor: String = "#FFF0F7",
    @Json(name = "isVisible") val isVisible: Boolean = true,
    @Json(name = "sortOrder") val sortOrder: Int = 0
)''')
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''    @Json(name = "title") val title: String = "",
    @Json(name = "description") val description: String = "",
    @Json(name = "buttonText") val buttonText: String = "تسوقي الآن",''',
'''    @Json(name = "title") val title: String = "",
    @Json(name = "arabicTitle") val arabicTitle: String = "",
    @Json(name = "description") val description: String = "",
    @Json(name = "buttonText") val buttonText: String = "تسوقي الآن",''')
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''data class HeroConfig(
    @Json(name = "slides") val slides: List<HeroSlideConfig> = emptyList()
)''',
'''data class HeroConfig(
    @Json(name = "slides") val slides: List<HeroSlideConfig> = emptyList(),
    @Json(name = "isVisible") val isVisible: Boolean = true
)''')
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''    @Json(name = "backgroundColor") val backgroundColor: String = "#121212",
    @Json(name = "textColor") val textColor: String = "#FFFFFF",''',
'''    // Empty means: preserve the storefront's own theme defaults.
    @Json(name = "backgroundColor") val backgroundColor: String = "",
    @Json(name = "textColor") val textColor: String = "",''')
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt'),
'''    @Json(name = "announcementColor") val announcementColor: String = "#381528",
    @Json(name = "favicon") val favicon: String = ""''',
'''    @Json(name = "announcementColor") val announcementColor: String = "#381528",
    @Json(name = "favicon") val favicon: String = "",
    @Json(name = "fontFamily") val fontFamily: String = ""''')

# WebsiteConfig defaults and CMS editable data.
replace(Path('app/src/main/java/com/pinky/dashboard/domain/model/StoreModels.kt'),
'''        SectionDisplayConfig("sec_announcement", "شريط التنبيهات العلوي", true, 1),
        SectionDisplayConfig("sec_hero", "البنر الرئيسي (Hero Section)", true, 2),
        SectionDisplayConfig("sec_categories", "أقسام المتجر الدائرية", true, 3),
        SectionDisplayConfig("sec_best_sellers", "المنتجات الأكثر مبيعاً", true, 4),
        SectionDisplayConfig("sec_offers", "عروض وتخفيضات Elory الحصرية", true, 5),
        SectionDisplayConfig("sec_prime_promo", "بنر الاشتراك في Elory Prime", true, 6),
        SectionDisplayConfig("sec_reviews", "آراء وتقييمات العملاء", true, 7),
        SectionDisplayConfig("sec_footer", "معلومات المتجر والتواصل والشحن", true, 8)
    ),''',
'''        SectionDisplayConfig("sec_announcement", "شريط التنبيهات العلوي", true, 1),
        SectionDisplayConfig("sec_hero", "البنر الرئيسي المتحرك", true, 2),
        SectionDisplayConfig("sec_categories", "أقسام المتجر الدائرية", true, 3),
        SectionDisplayConfig("sec_best_sellers", "المنتجات المميزة", true, 4),
        SectionDisplayConfig("sec_prime_promo", "بنر الاشتراك في Elory Prime", true, 5),
        SectionDisplayConfig("sec_features", "لماذا Elory؟", true, 6),
        SectionDisplayConfig("sec_final_cta", "الدعوة لاتخاذ إجراء", true, 7),
        SectionDisplayConfig("sec_footer", "معلومات المتجر والتواصل والشحن", true, 8)
    ),
    val heroSlides: List<HeroSlideConfig> = listOf(
        HeroSlideConfig("hero_1", "", "Your Style", "Discover", "أناقتكِ تبدأ من هنا", "اكتشفي أحدث صيحات الموضة والجمال", "تسوقي الآن", "#featured", 1, true),
        HeroSlideConfig("hero_2", "", "Elory COLLECTION", "Luxury Everyday", "", "شنط وإكسسوارات تضيف لمسة فاخرة إلى يومك.", "اكتشفي الشنط", "#featured", 2, true),
        HeroSlideConfig("hero_3", "", "NEW COLLECTION", "Your Style", "", "تفاصيل صغيرة تصنع إطلالة مختلفة.", "اكتشفي المجموعة", "#featured", 3, true)
    ),
    val customSections: List<CustomSiteSectionConfig> = emptyList(),''')

# Fix bucket identifiers to match the real project bucket.
replace(Path('app/src/main/java/com/pinky/dashboard/data/remote/SupabaseConfig.kt'),
'''    const val BUCKET_PRODUCT_IMAGES = "pinky-products"
    const val BUCKET_BANNERS = "pinky-banners"''',
'''    const val BUCKET_PRODUCT_IMAGES = "product-images"
    const val BUCKET_BANNERS = BUCKET_PRODUCT_IMAGES''')

# Replace save model mapping to persist hero, section visibility/order, and custom blocks.
pv = root / Path('app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt')
s = pv.read_text(encoding='utf-8')
old='''                val sectionsStr = config.sections.joinToString(";") { "${it.id}:${it.title}:${it.isVisible}:${it.sortOrder}" }
                
                val siteConfigObj = SiteCustomizationConfig(
                    announcement = AnnouncementConfig('''
new='''                val siteConfigObj = SiteCustomizationConfig(
                    announcement = AnnouncementConfig('''
if old not in s: raise SystemExit('PinkyViewModel sectionsStr anchor missing')
s=s.replace(old,new,1)
old='''                    navigation = config.navigationItems,
                    categories = CategoriesConfig('''
new='''                    navigation = config.navigationItems,
                    sections = config.sections.sortedBy { it.sortOrder }.map {
                        SiteSectionConfig(it.id, it.title, it.isVisible, it.sortOrder)
                    },
                    hero = HeroConfig(
                        slides = config.heroSlides.sortedBy { it.sortOrder },
                        isVisible = config.showHeroBanner
                    ),
                    customSections = config.customSections.sortedBy { it.sortOrder },
                    categories = CategoriesConfig('''
if old not in s: raise SystemExit('PinkyViewModel navigation anchor missing')
s=s.replace(old,new,1)
old='''                        backgroundColor = "#121212",
                        textColor = "#FFFFFF",
                        announcementColor = config.announcementBgColor'''
new='''                        backgroundColor = "",
                        textColor = "",
                        announcementColor = config.announcementBgColor,
                        fontFamily = config.fontFamily'''
if old not in s: raise SystemExit('PinkyViewModel global colors anchor missing')
s=s.replace(old,new,1)
# Load CMS data from the JSONB config, using old defaults when fields aren't present.
old='''                            sections = parsedSections ?: currentConfig.sections,

                            // Top Bar Announcement Multi-Messages'''
new='''                            sections = cfgObj?.sections?.map {
                                SectionDisplayConfig(it.id, it.title, it.isVisible, it.sortOrder)
                            } ?: parsedSections ?: currentConfig.sections,
                            heroSlides = cfgObj?.hero?.slides?.takeIf { it.isNotEmpty() } ?: currentConfig.heroSlides,
                            customSections = cfgObj?.customSections ?: currentConfig.customSections,

                            // Top Bar Announcement Multi-Messages'''
if old not in s: raise SystemExit('PinkyViewModel load sections anchor missing')
s=s.replace(old,new,1)
pv.write_text(s,encoding='utf-8')

# Wire the new controls into the existing editor UI.
pe = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
s=pe.read_text(encoding='utf-8')
old='''                    item {
                        SectionCard(
                            title = "إعدادات عامة وألوان وهوية الموقع",
                            description = "اسم المتجر، تفاصيل السيو والبحث، والخطوط ولون الهوية الأساسي",
                            icon = Icons.Outlined.SettingsSuggest,
                            isActive = true,
                            onToggleActive = null,
                            onClick = { activeEditingDialog = 11 }
                        )
                    }

                    item {
                        Spacer(modifier = Modifier.height(80.dp))
                    }'''
new='''                    item {
                        SectionCard(
                            title = "إعدادات عامة وألوان وهوية الموقع",
                            description = "اسم المتجر، تفاصيل السيو والبحث، والخطوط ولون الهوية الأساسي",
                            icon = Icons.Outlined.SettingsSuggest,
                            isActive = true,
                            onToggleActive = null,
                            onClick = { activeEditingDialog = 11 }
                        )
                    }

                    item {
                        Spacer(modifier = Modifier.height(80.dp))
                    }'''
if old not in s: raise SystemExit('WebsiteEditor card 11 anchor missing')
s=s.replace(old,new,1)
s=s.replace('''                    11 -> "هوية وإعدادات الموقع العامة" to Icons.Outlined.SettingsSuggest
                    else ->''','''                    11 -> "هوية وإعدادات الموقع العامة" to Icons.Outlined.SettingsSuggest
                    else ->''',1)
s=s.replace('''                        4 -> HeroBannersForm(bannersList, onSaveBanner, onDeleteBanner, categoriesList)''','''                        4 -> HeroBannersForm(dialogConfig, onUpdate = { dialogConfig = it })''',1)
s=s.replace('''                        11 -> GlobalSettingsForm(dialogConfig, onUpdate = { dialogConfig = it })''','''                        11 -> GlobalSettingsForm(dialogConfig, onUpdate = { dialogConfig = it })
                        ''',1)
start=s.index('@Composable\nfun HeroBannersForm(')
end=s.index('\n@Composable\nfun CategoriesLayoutForm',start)
new_hero='''@Composable
fun HeroBannersForm(
    config: WebsiteConfig,
    onUpdate: (WebsiteConfig) -> Unit
) {
    val slides = config.heroSlides.sortedBy { it.sortOrder }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("شرائح الهيرو المتحرك", fontWeight = FontWeight.Bold, fontSize = 16.sp)
        Text(
            "كل شريحة يمكن تعديل صورتها ونصوصها وزرها ورابطها وترتيبها. اترك الصورة فارغة للاحتفاظ بالصورة الافتراضية الحالية.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        slides.forEachIndexed { index, slide ->
            Card(
                modifier = Modifier.fillMaxWidth(),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("الشريحة ${index + 1}", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Switch(checked = slide.isActive, onCheckedChange = { active ->
                            val updated = slides.map { if (it.id == slide.id) it.copy(isActive = active) else it }
                            onUpdate(config.copy(heroSlides = updated))
                        })
                        IconButton(enabled = index > 0, onClick = {
                            val mutable = slides.toMutableList()
                            val item = mutable.removeAt(index); mutable.add(index - 1, item)
                            onUpdate(config.copy(heroSlides = mutable.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.ArrowUpward, contentDescription = "تحريك لأعلى") }
                        IconButton(enabled = index < slides.lastIndex, onClick = {
                            val mutable = slides.toMutableList()
                            val item = mutable.removeAt(index); mutable.add(index + 1, item)
                            onUpdate(config.copy(heroSlides = mutable.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.ArrowDownward, contentDescription = "تحريك لأسفل") }
                        IconButton(onClick = {
                            onUpdate(config.copy(heroSlides = slides.filterNot { it.id == slide.id }.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.Delete, contentDescription = "حذف الشريحة", tint = MaterialTheme.colorScheme.error) }
                    }
                    ImageUploadSelector(
                        imageUrl = slide.imageUrl,
                        onUrlChanged = { url -> onUpdate(config.copy(heroSlides = slides.map { if (it.id == slide.id) it.copy(imageUrl = url) else it })) },
                        bucket = "product-images",
                        placeholderText = "اختيار صورة الشريحة"
                    )
                    OutlinedTextField(value = slide.smallText, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(smallText=v) else it })) }, label = { Text("النص الصغير") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = slide.title, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(title=v) else it })) }, label = { Text("العنوان الرئيسي") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = slide.arabicTitle, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(arabicTitle=v) else it })) }, label = { Text("العنوان العربي") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = slide.description, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(description=v) else it })) }, label = { Text("الوصف") }, modifier = Modifier.fillMaxWidth(), minLines = 2)
                    OutlinedTextField(value = slide.buttonText, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(buttonText=v) else it })) }, label = { Text("نص الزر") }, modifier = Modifier.fillMaxWidth())
                    OutlinedTextField(value = slide.actionUrl, onValueChange = { v -> onUpdate(config.copy(heroSlides = slides.map { if(it.id==slide.id) it.copy(actionUrl=v) else it })) }, label = { Text("رابط الزر (مثل #featured)") }, modifier = Modifier.fillMaxWidth())
                }
            }
        }
        Button(
            onClick = {
                val updated = slides + HeroSlideConfig(
                    id = "hero_${System.currentTimeMillis()}", imageUrl = "", smallText = "NEW COLLECTION",
                    title = "عنوان جديد", arabicTitle = "", description = "اكتب وصف الشريحة هنا",
                    buttonText = "اكتشفي الآن", actionUrl = "#featured", sortOrder = slides.size + 1, isActive = true
                )
                onUpdate(config.copy(heroSlides = updated))
            },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
        ) { Icon(Icons.Filled.Add, contentDescription = null); Spacer(Modifier.width(6.dp)); Text("إضافة شريحة جديدة") }
    }
}
'''
s=s[:start]+new_hero+s[end:]
# Add section layout form before CategoriesLayoutForm.
anchor='\n@Composable\nfun CategoriesLayoutForm'
layout='''
@Composable
fun SectionsLayoutForm(config: WebsiteConfig, onUpdate: (WebsiteConfig) -> Unit) {
    var editingCustom by remember { mutableStateOf<CustomSiteSectionConfig?>(null) }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Text("ترتيب وأقسام الصفحة الرئيسية", fontWeight = FontWeight.Bold, fontSize = 16.sp)
        Text("استخدم مفاتيح الظهور لإخفاء الأقسام، والأسهم لتغيير ترتيبها. الحفظ ينشر الإعدادات إلى الموقع.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        val sections = config.sections.sortedBy { it.sortOrder }
        sections.forEachIndexed { index, section ->
            Card(border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant)) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(section.title, fontWeight = FontWeight.SemiBold)
                        if (section.id.startsWith("custom_")) Text("قسم مخصص", style = MaterialTheme.typography.labelSmall, color = PinkPrimary)
                    }
                    Switch(checked = section.isVisible, onCheckedChange = { visible ->
                        onUpdate(config.copy(sections = sections.map { if(it.id==section.id) it.copy(isVisible=visible) else it }))
                    })
                    IconButton(enabled = index > 0, onClick = {
                        val list=sections.toMutableList(); val item=list.removeAt(index); list.add(index-1,item)
                        onUpdate(config.copy(sections=list.mapIndexed { i,v -> v.copy(sortOrder=i+1) }))
                    }) { Icon(Icons.Filled.ArrowUpward, contentDescription = "لأعلى") }
                    IconButton(enabled = index < sections.lastIndex, onClick = {
                        val list=sections.toMutableList(); val item=list.removeAt(index); list.add(index+1,item)
                        onUpdate(config.copy(sections=list.mapIndexed { i,v -> v.copy(sortOrder=i+1) }))
                    }) { Icon(Icons.Filled.ArrowDownward, contentDescription = "لأسفل") }
                    if (section.id.startsWith("custom_")) {
                        IconButton(onClick = { editingCustom = config.customSections.find { it.id == section.id.removePrefix("custom_") } }) {
                            Icon(Icons.Filled.Edit, contentDescription = "تعديل القسم", tint = PinkPrimary)
                        }
                        IconButton(onClick = {
                            val id = section.id.removePrefix("custom_")
                            onUpdate(config.copy(sections=sections.filterNot { it.id==section.id }.mapIndexed { i,v -> v.copy(sortOrder=i+1) }, customSections=config.customSections.filterNot { it.id==id }))
                        }) { Icon(Icons.Filled.Delete, contentDescription = "حذف القسم", tint = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
        Button(onClick = {
            editingCustom = CustomSiteSectionConfig(
                id = "${System.currentTimeMillis()}", title = "قسم جديد", text = "اكتب محتوى القسم هنا",
                sortOrder = sections.size + 1
            )
        }, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))) {
            Icon(Icons.Filled.Add, contentDescription = null); Spacer(Modifier.width(6.dp)); Text("إضافة قسم مخصص")
        }
    }

    editingCustom?.let { initial ->
        var local by remember(initial.id) { mutableStateOf(initial) }
        AlertDialog(
            onDismissRequest = { editingCustom = null },
            title = { Text("إعداد القسم المخصص") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(local.title, { local=local.copy(title=it) }, label={ Text("عنوان القسم") }, modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(local.text, { local=local.copy(text=it) }, label={ Text("النص") }, modifier=Modifier.fillMaxWidth(), minLines=3)
                    OutlinedTextField(local.imageUrl, { local=local.copy(imageUrl=it) }, label={ Text("رابط الصورة (اختياري)") }, modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(local.buttonText, { local=local.copy(buttonText=it) }, label={ Text("نص الزر (اختياري)") }, modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(local.buttonUrl, { local=local.copy(buttonUrl=it) }, label={ Text("رابط الزر") }, modifier=Modifier.fillMaxWidth())
                    OutlinedTextField(local.backgroundColor, { local=local.copy(backgroundColor=it) }, label={ Text("لون الخلفية Hex") }, modifier=Modifier.fillMaxWidth())
                    Row(verticalAlignment=Alignment.CenterVertically) { Text("إظهار القسم", modifier=Modifier.weight(1f)); Switch(local.isVisible, { local=local.copy(isVisible=it) }) }
                }
            },
            confirmButton = { TextButton(onClick = {
                val exists = config.customSections.any { it.id == local.id }
                val custom = if(exists) config.customSections.map { if(it.id==local.id) local else it } else config.customSections + local.copy(sortOrder=config.sections.size+1)
                val secId = "custom_${local.id}"
                val section = SectionDisplayConfig(secId, local.title, local.isVisible, local.sortOrder.coerceAtLeast(1))
                val sections = if(config.sections.any { it.id==secId }) config.sections.map { if(it.id==secId) section else it } else config.sections + section
                onUpdate(config.copy(customSections=custom, sections=sections.mapIndexed { i,v -> v.copy(sortOrder = if(v.id==secId) section.sortOrder else v.sortOrder) }))
                editingCustom=null
            }) { Text("حفظ القسم") } },
            dismissButton = { TextButton(onClick={ editingCustom=null }) { Text("إلغاء") } }
        )
    }
}
'''
if anchor not in s: raise SystemExit('CategoriesLayoutForm anchor missing')
s=s.replace(anchor, '\n'+layout+anchor, 1)
# Replace wrong bucket parameters globally in WebsiteEditorScreen.
s=s.replace('bucket = "pinky-products"','bucket = "product-images"')
s=s.replace('bucket = "pinky-banners"','bucket = "product-images"')
# Replace direct Supabase image uploader implementation with shared compressed uploader.
s=s.replace('import com.pinky.dashboard.data.remote.SupabaseClient','import com.pinky.dashboard.data.remote.SupabaseClient\nimport com.pinky.dashboard.data.remote.SupabaseStorageUploader')
start=s.index('@Composable\nfun ImageUploadSelector(')
# replace function through EOF? function is last. verify last closing
new_img='''@Composable
fun ImageUploadSelector(
    imageUrl: String,
    onUrlChanged: (String) -> Unit,
    bucket: String,
    placeholderText: String
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isUploading by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    var uploadSuccess by remember { mutableStateOf(false) }

    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        if (uri != null && !isUploading) {
            isUploading = true
            uploadError = null
            uploadSuccess = false
            scope.launch {
                try {
                    val uploadedUrl = SupabaseStorageUploader.uploadProductImage(
                        contentResolver = context.contentResolver,
                        uri = uri,
                        productId = "site-assets",
                        label = "website"
                    )
                    onUrlChanged(uploadedUrl)
                    uploadSuccess = true
                } catch (e: Exception) {
                    uploadError = e.message ?: "تعذر رفع الصورة. تحقق من صلاحية الحساب والاتصال."
                    android.util.Log.e("EloryWebsiteUpload", "Image upload failed", e)
                } finally {
                    isUploading = false
                }
            }
        }
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (imageUrl.isNotBlank()) {
            AsyncImage(
                model = imageUrl,
                contentDescription = null,
                modifier = Modifier.fillMaxWidth().height(150.dp).clip(RoundedCornerShape(10.dp)),
                contentScale = ContentScale.Crop
            )
        }
        OutlinedButton(
            onClick = { photoPickerLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            enabled = !isUploading,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(8.dp)
        ) {
            if (isUploading) CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
            else Icon(Icons.Outlined.CloudUpload, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (isUploading) "جاري ضغط ورفع الصورة..." else placeholderText)
        }
        if (uploadSuccess) Text("تم رفع الصورة بنجاح", color = Color(0xFF2E8B57), style = MaterialTheme.typography.bodySmall)
        uploadError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        OutlinedTextField(
            value = imageUrl,
            onValueChange = onUrlChanged,
            label = { Text("رابط الصورة (اختياري)") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true
        )
    }
}
'''
s=s[:start]+new_img
pe.write_text(s,encoding='utf-8')

# Persist and display the actual result of the asynchronous website save.
pv = root / Path('app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt')
s = pv.read_text(encoding='utf-8')
old = '''    private val _websiteConfig = MutableStateFlow(WebsiteConfig())
    val websiteConfig: StateFlow<WebsiteConfig> = _websiteConfig.asStateFlow()'''
new = old + '''
    private val _websiteSaveState = MutableStateFlow("idle")
    val websiteSaveState: StateFlow<String> = _websiteSaveState.asStateFlow()'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''    fun updateWebsiteConfig(config: WebsiteConfig) {
        viewModelScope.launch {
            try {'''
new='''    fun updateWebsiteConfig(config: WebsiteConfig) {
        viewModelScope.launch {
            _websiteSaveState.value = "saving"
            try {'''
assert s.count(old)==1
s=s.replace(old,new,1)
old='''                    )
                    return@launch
                }
                _websiteConfig.value = config
            } catch (e: Exception) {
                android.util.Log.e("PinkyViewModel", "Exception in updateWebsiteConfig", e)
                e.printStackTrace()
            }
        }
    }'''
new='''                    )
                    _websiteSaveState.value = "error"
                    return@launch
                }
                _websiteConfig.value = config
                _websiteSaveState.value = "success"
            } catch (e: Exception) {
                android.util.Log.e("PinkyViewModel", "Exception in updateWebsiteConfig", e)
                e.printStackTrace()
                _websiteSaveState.value = "error"
            }
        }
    }'''
assert s.count(old)==1
s=s.replace(old,new,1)
pv.write_text(s,encoding='utf-8')

app_file = root / Path('app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt')
app_source = app_file.read_text(encoding='utf-8')
old='''    val websiteConfig by viewModel.websiteConfig.collectAsStateWithLifecycle()'''
assert app_source.count(old)==1
app_source=app_source.replace(old,old+'''\n    val websiteSaveState by viewModel.websiteSaveState.collectAsStateWithLifecycle()''',1)
old='''                                    onSaveConfig = { viewModel.updateWebsiteConfig(it) },'''
assert app_source.count(old)==1
app_source=app_source.replace(old,old+'''\n                                    saveState = websiteSaveState,''',1)
app_file.write_text(app_source,encoding='utf-8')

pe = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
s=pe.read_text(encoding='utf-8')
old='''    onSaveCategory: (Category) -> Unit,
    modifier: Modifier = Modifier
) {'''
assert s.count(old)==1
s=s.replace(old,'''    onSaveCategory: (Category) -> Unit,
    saveState: String = "idle",
    modifier: Modifier = Modifier
) {''',1)
old='''    Scaffold(
        floatingActionButton = {'''
assert s.count(old)==1
s=s.replace(old,'''    LaunchedEffect(saveState) {
        showSavedMessage = saveState == "success" || saveState == "error"
    }

    Scaffold(
        floatingActionButton = {''',1)
s=s.replace('''                onClick = {
                    onSaveConfig(config)
                    showSavedMessage = true
                },''','''                onClick = {
                    onSaveConfig(config)
                },''',1)
s=s.replace('''                text = { Text("حفظ ونشر التعديلات", fontWeight = FontWeight.Bold) },''','''                text = { Text(if (saveState == "saving") "جارٍ حفظ التعديلات..." else "حفظ ونشر التعديلات", fontWeight = FontWeight.Bold) },''',1)
s=s.replace('''                    Text("تم حفظ إعدادات موقع Elory بنجاح وستنعكس للمتسوقين فوراً.")''','''                    Text(if (saveState == "success") "تم حفظ إعدادات الموقع بنجاح." else "تعذر حفظ جميع إعدادات الموقع. راجع الاتصال والصلاحيات ثم أعد المحاولة.")''',1)
s=s.replace('import com.pinky.dashboard.data.remote.SupabaseClient\n','')
s=s.replace('import okhttp3.MediaType.Companion.toMediaTypeOrNull\n','')
pe.write_text(s,encoding='utf-8')

cat_file = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/categories/CategoriesScreen.kt')
cat_source=cat_file.read_text(encoding='utf-8')
assert cat_source.count('val bucket = "pinky-products"')==1
cat_file.write_text(cat_source.replace('val bucket = "pinky-products"','val bucket = "product-images"',1),encoding='utf-8')
# Use the same secured, compressed image uploader for custom content sections.
pe = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
s = pe.read_text(encoding='utf-8')
old = '''                    OutlinedTextField(local.imageUrl, { local=local.copy(imageUrl=it) }, label={ Text("رابط الصورة (اختياري)") }, modifier=Modifier.fillMaxWidth())'''
new = '''                    ImageUploadSelector(
                        imageUrl = local.imageUrl,
                        onUrlChanged = { local = local.copy(imageUrl = it) },
                        bucket = "product-images",
                        placeholderText = "رفع صورة القسم"
                    )'''
assert s.count(old) == 1
pe.write_text(s.replace(old,new,1), encoding='utf-8')

# Persist the hero's visibility toggle and reflect it when loading the CMS config.
pv = root / Path('app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt')
s = pv.read_text(encoding='utf-8')
old = "showHeroBanner = customizations.showHeroBanner,"
assert s.count(old) == 1
s = s.replace(old, "showHeroBanner = cfgObj?.hero?.isVisible ?: customizations.showHeroBanner,", 1)
pv.write_text(s, encoding='utf-8')

remote_file = root / Path('app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt')
remote_source = remote_file.read_text(encoding='utf-8')
old = '''    val showHeroBanner: Boolean
        get() = config?.hero?.slides?.any { it.isActive } ?: true'''
new = '''    val showHeroBanner: Boolean
        get() = config?.hero?.isVisible ?: (config?.hero?.slides?.any { it.isActive } ?: true)'''
assert remote_source.count(old) == 1
remote_file.write_text(remote_source.replace(old,new,1), encoding='utf-8')

# Announcement and footer are outside the home content container, so do not offer non-functional reorder controls.
pe = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
s = pe.read_text(encoding='utf-8')
start = s.index('fun SectionsLayoutForm(')
end = s.index('\n@Composable\nfun CategoriesLayoutForm', start)
block = s[start:end]
old = 'IconButton(enabled = index > 0, onClick = {'
assert block.count(old) == 1
block = block.replace(old, 'val canReorder = section.id !in setOf(\"sec_announcement\", \"sec_footer\")\n                    IconButton(enabled = canReorder && index > 0, onClick = {', 1)
old = 'IconButton(enabled = index < sections.lastIndex, onClick = {'
assert block.count(old) == 1
block = block.replace(old, 'IconButton(enabled = canReorder && index < sections.lastIndex, onClick = {', 1)
s = s[:start] + block + s[end:]
pe.write_text(s, encoding='utf-8')

pe = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
s = pe.read_text(encoding='utf-8')
old = '''                    Switch(checked = section.isVisible, onCheckedChange = { visible ->
                        onUpdate(config.copy(sections = sections.map { if(it.id==section.id) it.copy(isVisible=visible) else it }))
                    })'''
new = '''                    Switch(checked = section.isVisible, onCheckedChange = { visible ->
                        val updatedCustomSections = if (section.id.startsWith("custom_")) {
                            val customId = section.id.removePrefix("custom_")
                            config.customSections.map { if (it.id == customId) it.copy(isVisible = visible) else it }
                        } else config.customSections
                        onUpdate(config.copy(
                            sections = sections.map { if (it.id == section.id) it.copy(isVisible = visible) else it },
                            customSections = updatedCustomSections
                        ))
                    })'''
assert s.count(old) == 1
pe.write_text(s.replace(old,new,1), encoding='utf-8')

screen_file = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
screen_text = screen_file.read_text(encoding='utf-8')
screen_package_match = re.search(r'^\s*package\s+([^\s]+)', screen_text, re.MULTILINE)
if not screen_package_match:
    raise SystemExit(f'Could not determine Kotlin package from {screen_file}')
screen_package = screen_package_match.group(1)
mockup_file = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/PhoneMockupView.kt')
mockup_source = r'''
package com.pinky.dashboard.ui.screens.website

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Category
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.pinky.dashboard.domain.model.Category
import com.pinky.dashboard.domain.model.Offer
import com.pinky.dashboard.domain.model.WebsiteConfig

private fun previewColor(value: String, fallback: Color): Color = try {
    Color(android.graphics.Color.parseColor(value))
} catch (_: Exception) { fallback }

@Composable
fun PhoneMockupView(
    config: WebsiteConfig,
    categories: List<Category>,
    banners: List<Offer>
) {
    val hero = config.heroSlides.firstOrNull { it.isActive }
    val headerBg = remember(config.headerBgColor) { previewColor(config.headerBgColor, Color.White) }
    val iconColor = remember(config.headerIconsColor) { previewColor(config.headerIconsColor, Color(0xFFC96F92)) }
    val announcementBg = remember(config.announcementBgColor) { previewColor(config.announcementBgColor, Color(0xFF381528)) }
    val announcementText = remember(config.announcementTextColor) { previewColor(config.announcementTextColor, Color.White) }

    Card(
        modifier = Modifier.widthIn(max = 380.dp).fillMaxHeight(0.95f),
        shape = RoundedCornerShape(34.dp),
        border = androidx.compose.foundation.BorderStroke(4.dp, Color(0xFF282328)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(Modifier.fillMaxSize().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Box(Modifier.width(68.dp).height(5.dp).clip(CircleShape).background(Color.Gray.copy(alpha = .35f)))
            Spacer(Modifier.height(12.dp))
            Column(Modifier.weight(1f).fillMaxWidth().verticalScroll(rememberScrollState())) {
                if (config.showAnnouncementBar) {
                    Box(Modifier.fillMaxWidth().background(announcementBg).padding(7.dp), contentAlignment = Alignment.Center) {
                        Text(config.announcementMsg1, color = announcementText, fontSize = 10.sp, textAlign = TextAlign.Center)
                    }
                }
                Row(Modifier.fillMaxWidth().background(headerBg).padding(10.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                    if (config.headerLogoUrl.isNotBlank()) {
                        AsyncImage(config.headerLogoUrl, null, Modifier.height(30.dp).widthIn(max = 100.dp), contentScale = ContentScale.Fit)
                    } else Text(config.storeName, color = iconColor, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                    Text("⌕   ♡   🛍", color = iconColor, fontSize = 14.sp)
                }
                if (config.showHeroBanner && hero != null) {
                    Column(Modifier.fillMaxWidth().padding(top = 10.dp).clip(RoundedCornerShape(14.dp)).background(Color(0xFFFFF0F5))) {
                        if (hero.imageUrl.isNotBlank()) AsyncImage(hero.imageUrl, null, Modifier.fillMaxWidth().height(135.dp), contentScale = ContentScale.Crop)
                        Column(Modifier.padding(12.dp)) {
                            Text(hero.smallText, color = Color(0xFF9D5574), fontSize = 9.sp, fontWeight = FontWeight.Bold)
                            Text(hero.title, fontSize = 18.sp, fontWeight = FontWeight.ExtraBold, color = Color(0xFF381528))
                            if (hero.arabicTitle.isNotBlank()) Text(hero.arabicTitle, fontWeight = FontWeight.Bold, color = Color(0xFF381528))
                            Text(hero.description, fontSize = 10.sp, color = Color.DarkGray)
                            Spacer(Modifier.height(6.dp))
                            Text(hero.buttonText, color = Color(0xFFC96F92), fontWeight = FontWeight.Bold, fontSize = 11.sp)
                        }
                    }
                }
                if (config.categoriesIsVisible) {
                    Column(Modifier.fillMaxWidth().padding(top = 14.dp)) {
                        Text(config.categoriesTitle, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                        Text(config.categoriesSubtitle, color = Color.Gray, fontSize = 9.sp)
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 8.dp)) {
                            items(categories.filter { it.isActive }) { category ->
                                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(58.dp)) {
                                    if (category.imageUrl.isNotBlank()) AsyncImage(category.imageUrl, null, Modifier.size(48.dp).clip(CircleShape), contentScale = ContentScale.Crop)
                                    else Box(Modifier.size(48.dp).clip(CircleShape).background(Color(0xFFF8E8EF)), contentAlignment = Alignment.Center) { Icon(Icons.Filled.Category, null, tint = iconColor) }
                                    Text(category.name, fontSize = 9.sp, textAlign = TextAlign.Center, maxLines = 2)
                                }
                            }
                        }
                    }
                }
                Column(Modifier.fillMaxWidth().padding(top = 10.dp)) {
                    Text(config.productsSectionTitle, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                    Text(config.productsSectionSubtitle, color = Color.Gray, fontSize = 9.sp)
                    if (banners.isNotEmpty()) Text("${banners.size} عروض متاحة", color = iconColor, fontSize = 10.sp)
                }
                if (config.primeIsVisible) {
                    Column(Modifier.fillMaxWidth().padding(top = 14.dp).clip(RoundedCornerShape(12.dp)).background(Color(0xFF381528)).padding(12.dp)) {
                        Text(config.primeName, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 13.sp)
                        Text(config.primeDescription, color = Color.White.copy(alpha = .8f), fontSize = 10.sp)
                    }
                }
                config.customSections.filter { it.isVisible }.sortedBy { it.sortOrder }.forEach { section ->
                    Column(Modifier.fillMaxWidth().padding(top = 12.dp).clip(RoundedCornerShape(12.dp)).background(previewColor(section.backgroundColor, Color(0xFFFFF0F5))).padding(12.dp)) {
                        if (section.imageUrl.isNotBlank()) AsyncImage(section.imageUrl, null, Modifier.fillMaxWidth().height(90.dp).clip(RoundedCornerShape(8.dp)), contentScale = ContentScale.Crop)
                        Text(section.title, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                        Text(section.text, fontSize = 10.sp)
                        if (section.buttonText.isNotBlank()) Text(section.buttonText, color = iconColor, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                    }
                }
            }
            Text("معاينة تقريبية للموقع على الهاتف", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 9.sp, modifier = Modifier.padding(top = 6.dp))
        }
    }
}

'''
mockup_source = mockup_source.replace(
    'package com.pinky.dashboard.ui.screens.website',
    f'package {screen_package}',
    1
)
mockup_file.write_text(mockup_source, encoding='utf-8')
if not mockup_file.is_file() or 'fun PhoneMockupView(' not in mockup_file.read_text(encoding='utf-8'):
    raise SystemExit('PhoneMockupView source was not generated correctly')

print(f'PhoneMockupView generated: {mockup_file} (package {screen_package})')


# Repair the website order JSON adapter and hydrate internal product data for owner/staff.
def patch_source(relative_path, old, new, label):
    source_path = root / relative_path
    if not source_path.is_file():
        raise SystemExit(f'Missing source file for {label}: {relative_path}')
    source_text = source_path.read_text(encoding='utf-8')
    if old not in source_text:
        raise SystemExit(f'Expected source anchor not found for {label}: {relative_path}')
    source_path.write_text(source_text.replace(old, new, 1), encoding='utf-8')

order_model = 'app/src/main/java/com/pinky/dashboard/domain/model/Order.kt'
patch_source(
    order_model,
    '    val imageUrl: String? = null\n)',
    '    val imageUrl: String? = null,\n    val productCode: String = "",\n    val wholesalePrice: Double? = null\n)',
    'order item internal fields'
)


entities_file = 'app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt'
entities_path = root / entities_file
entities_text = entities_path.read_text(encoding='utf-8')
if 'import androidx.room.ColumnInfo' not in entities_text:
    entities_text = entities_text.replace(
        'import androidx.room.Entity\n',
        'import androidx.room.ColumnInfo\nimport androidx.room.Entity\n',
        1
    )
old_entity_end = """    val imageUrl: String?
)"""
new_entity_end = """    val imageUrl: String?,
    @ColumnInfo(defaultValue = "''") val productCode: String = "",
    val wholesalePrice: Double? = null
)"""
if old_entity_end not in entities_text:
    raise SystemExit('OrderItemEntity fields anchor not found')
entities_text = entities_text.replace(old_entity_end, new_entity_end, 1)
entities_path.write_text(entities_text, encoding='utf-8')

database_file = 'app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt'
database_path = root / database_file
database_text = database_path.read_text(encoding='utf-8')
if 'import androidx.room.migration.Migration' not in database_text:
    database_text = database_text.replace(
        'import androidx.room.RoomDatabase\n',
        'import androidx.room.RoomDatabase\nimport androidx.room.migration.Migration\n',
        1
    )
database_text = database_text.replace('    version = 3,', '    version = 4,', 1)
old_instance = """        private var INSTANCE: PinkyDatabase? = null
"""
new_instance = """        private var INSTANCE: PinkyDatabase? = null

        private val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(database: SupportSQLiteDatabase) {
                database.execSQL("ALTER TABLE order_items ADD COLUMN productCode TEXT NOT NULL DEFAULT ''")
                database.execSQL("ALTER TABLE order_items ADD COLUMN wholesalePrice REAL")
            }
        }
"""
if old_instance not in database_text:
    raise SystemExit('PinkyDatabase migration insertion anchor not found')
database_text = database_text.replace(old_instance, new_instance, 1)
database_text = database_text.replace(
    '                .fallbackToDestructiveMigration()',
    '                .addMigrations(MIGRATION_3_4)\n                .fallbackToDestructiveMigration()',
    1
)
database_path.write_text(database_text, encoding='utf-8')

supabase_client = 'app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt'
patch_source(
    supabase_client,
    '    @Json(name = "image_url") val imageUrl: String? = null\n)',
    '    @Json(name = "image_url") val imageUrl: String? = null,\n'
    '    // The storefront JSONB item schema uses name/price/image/code.\n'
    '    @Json(name = "name") val name: String? = null,\n'
    '    @Json(name = "price") val price: Double? = null,\n'
    '    @Json(name = "image") val image: String? = null,\n'
    '    @Json(name = "code") val code: String? = null,\n'
    '    @Json(name = "wholesale_price") val wholesalePrice: Double? = null,\n'
    '    @Json(name = "product_code") val productCode: String? = null,\n'
    '    @Json(name = "product_image") val productImage: String? = null\n)',
    'storefront order item JSON aliases'
)
patch_source(
    supabase_client,
    '    @POST("rest/v1/shipping_governorates")\n'
    '    suspend fun upsertGovernorate(\n'
    '        @Body gov: SupabaseGovernorateDto,\n'
    '        @Header("Prefer") prefer: String = "resolution=merge-duplicates"\n'
    '    ): Response<Unit>\n',
    '    @POST("rest/v1/shipping_governorates")\n'
    '    suspend fun upsertGovernorate(\n'
    '        @Body gov: SupabaseGovernorateDto,\n'
    '        @Header("Prefer") prefer: String = "resolution=merge-duplicates"\n'
    '    ): Response<Unit>\n\n'
    '    @POST("rest/v1/rpc/admin_save_shipping_governorate")\n'
    '    suspend fun saveShippingGovernorate(\n'
    '        @Body params: Map<String, Any>\n'
    '    ): Response<Map<String, Any>>\n',
    'transactional governorate save RPC'
)

repo_file = 'app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt'
repo_path = root / repo_file
repo_text = repo_path.read_text(encoding='utf-8')
if 'import kotlinx.coroutines.flow.first' not in repo_text:
    repo_text = repo_text.replace(
        'package com.pinky.dashboard.data.repository\n',
        'package com.pinky.dashboard.data.repository\n\nimport kotlinx.coroutines.flow.first\n',
        1
    )
order_class_index = repo_text.index('class OrderRepositoryImpl(')
order_dao_line = '    private val orderDao = database.orderDao()\n'
order_dao_index = repo_text.find(order_dao_line, order_class_index)
if order_dao_index < 0:
    raise SystemExit('OrderRepositoryImpl orderDao anchor not found')
next_class_index = repo_text.find('class ', order_class_index + 1)
if next_class_index < 0:
    next_class_index = len(repo_text)
if 'private val productDao = database.productDao()' not in repo_text[order_class_index:next_class_index]:
    insert_at = order_dao_index + len(order_dao_line)
    repo_text = repo_text[:insert_at] + '    private val productDao = database.productDao()\n' + repo_text[insert_at:]
repo_text = repo_text.replace(
    'return orderDao.getAllOrdersFlow().map { entities ->',
    'return combine(orderDao.getAllOrdersFlow(), productDao.getAllProductsFlow()) { entities, products ->\n'
    '            val productsById = products.associateBy { it.id }',
    1
)
repo_text = repo_text.replace(
    'val items = orderDao.getOrderItems(entity.id).map { itemEntity ->\n                    OrderItem(',
    'val items = orderDao.getOrderItems(entity.id).map { itemEntity ->\n'
    '                    val product = productsById[itemEntity.productId]\n'
    '                    OrderItem(',
    1
)
repo_text = repo_text.replace(
    'val items = orderDao.getOrderItems(entity.id).map { itemEntity ->\n            OrderItem(',
    'val items = orderDao.getOrderItems(entity.id).map { itemEntity ->\n'
    '            val product = productDao.getProductById(itemEntity.productId)\n'
    '            OrderItem(',
    1
)
repo_text = repo_text.replace(
    'productName = itemEntity.productName,',
    'productName = itemEntity.productName.ifBlank { product?.name.orEmpty() },',
    2
)
repo_text = repo_text.replace(
    'imageUrl = itemEntity.imageUrl',
    'imageUrl = itemEntity.imageUrl?.takeIf { it.isNotBlank() } ?: product?.imageUrl.orEmpty(),\n'
    '                        productCode = itemEntity.productCode.ifBlank { product?.internalCode.orEmpty() },\n'
    '                        wholesalePrice = itemEntity.wholesalePrice ?: product?.wholesalePrice',
    2
)
repo_text = repo_text.replace(
    'productName = item.productName ?: "",',
    'productName = item.productName?.takeIf { it.isNotBlank() } ?: item.name?.takeIf { it.isNotBlank() } ?: product?.name.orEmpty(),',
    1
)
repo_text = repo_text.replace(
    'unitPrice = item.unitPrice ?: 0.0,',
    'unitPrice = item.unitPrice ?: item.price ?: 0.0,',
    1
)
repo_text = repo_text.replace(
    'lineTotal = item.lineTotal ?: 0.0,',
    'lineTotal = item.lineTotal ?: ((item.unitPrice ?: item.price ?: 0.0) * (item.quantity ?: 1)),',
    1
)
repo_text = repo_text.replace(
    'imageUrl = item.imageUrl ?: ""',
    'imageUrl = item.productImage?.takeIf { it.isNotBlank() } ?: item.imageUrl?.takeIf { it.isNotBlank() } ?: item.image?.takeIf { it.isNotBlank() } ?: product?.imageUrl,\n'
    '                            productCode = item.productCode?.takeIf { it.isNotBlank() } ?: item.code?.takeIf { it.isNotBlank() } ?: product?.internalCode.orEmpty(),\n'
    '                            wholesalePrice = item.wholesalePrice ?: product?.wholesalePrice',
    1
)
repo_text = repo_text.replace(
    '                    dto.items?.map { item ->\n                        OrderItemEntity(',
    '                    dto.items?.map { item ->\n'
    '                        val product = productDao.getProductById(item.productId ?: "")\n'
    '                        OrderItemEntity(',
    1
)
repo_path.write_text(repo_text, encoding='utf-8')

order_dialog = 'app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt'
dialog_path = root / order_dialog
dialog_text = dialog_path.read_text(encoding='utf-8')
if 'import coil.compose.AsyncImage' not in dialog_text:
    dialog_text = dialog_text.replace(
        'import androidx.compose.ui.graphics.Color\n',
        'import androidx.compose.ui.graphics.Color\n'
        'import androidx.compose.ui.layout.ContentScale\n'
        'import coil.compose.AsyncImage\n',
        1
    )
dialog_text = dialog_text.replace(
    '    onStatusChange: (OrderStatus) -> Unit\n) {',
    '    onStatusChange: (OrderStatus) -> Unit,\n'
    '    canViewWholesale: Boolean = false,\n'
    '    canViewInternalCode: Boolean = false\n) {',
    1
)
image_block = """                                if (!item.imageUrl.isNullOrBlank()) {
                                    AsyncImage(
                                        model = item.imageUrl,
                                        contentDescription = item.productName,
                                        modifier = Modifier.size(64.dp).clip(RoundedCornerShape(10.dp)),
                                        contentScale = ContentScale.Crop
                                    )
                                } else {
                                    Box(
                                        modifier = Modifier.size(64.dp).clip(RoundedCornerShape(10.dp))
                                            .background(MaterialTheme.colorScheme.surfaceVariant),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Icon(Icons.Outlined.Image, contentDescription = "صورة المنتج غير متاحة",
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
"""
dialog_text = dialog_text.replace(image_block, '', 1)
items_start = dialog_text.index('items(order.items, key = { it.id })')
column_marker = '                                Column(modifier = Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {'
column_index = dialog_text.index(column_marker, items_start)
dialog_text = dialog_text[:column_index] + image_block + dialog_text[column_index:]
dialog_text = dialog_text.replace(
    '                                    Text(item.productName, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)\n',
    '                                    Text(item.productName.ifBlank { "منتج غير معروف" }, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)\n'
    '                                    if (canViewInternalCode && item.productCode.isNotBlank()) {\n'
    '                                        Text("كود المنتج: ${item.productCode}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n'
    '                                    }\n'
    '                                    if (canViewWholesale && item.wholesalePrice != null) {\n'
    '                                        Text("سعر الجملة: ${Formatters.formatCurrencyEgp(item.wholesalePrice)}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.tertiary)\n'
    '                                    }\n',
    1
)
dialog_path.write_text(dialog_text, encoding='utf-8')

pinky_app = 'app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt'
patch_source(
    pinky_app,
    '                    order = order,\n'
    '                    onDismiss = { viewModel.selectOrder(null) },',
    '                    order = order,\n'
    '                    canViewWholesale = currentUser?.canViewWholesale == true,\n'
    '                    canViewInternalCode = currentUser?.canViewInternalCode == true,\n'
    '                    onDismiss = { viewModel.selectOrder(null) },',
    'order dialog permission wiring'
)

# Governorate price saves now use the transactional RPC which also updates existing centers.
repo_text = repo_path.read_text(encoding='utf-8')
old_save = (
    'val response = SupabaseClient.service.upsertGovernorate(\n'
    '                SupabaseGovernorateDto(\n'
    '                    governorate = gov.name,\n'
    '                    price = gov.deliveryPrice,\n'
    '                    centersEnabled = true,\n'
    '                    active = gov.isActive\n'
    '                )\n'
    '            )'
)
new_save = (
    'val response = SupabaseClient.service.saveShippingGovernorate(\n'
    '                mapOf(\n'
    '                    "p_governorate" to gov.name,\n'
    '                    "p_price" to gov.deliveryPrice,\n'
    '                    "p_active" to gov.isActive,\n'
    '                    "p_centers_enabled" to true\n'
    '                )\n'
    '            )'
)
if old_save not in repo_text:
    raise SystemExit('Governorate save source anchor not found')
repo_text = repo_text.replace(old_save, new_save, 1)
old_local = (
    '            shippingDao.insertGovernorate(\n'
    '                ShippingGovernorateEntity(gov.id, gov.name, gov.deliveryPrice, gov.estimatedDays, gov.isActive)\n'
    '            )\n'
    '            Result.success(gov)'
)
new_local = (
    '            shippingDao.insertGovernorate(\n'
    '                ShippingGovernorateEntity(gov.id, gov.name, gov.deliveryPrice, gov.estimatedDays, gov.isActive)\n'
    '            )\n'
    '            val updatedCenterCount = (response.body()?.get("updated_centers") as? Number)?.toInt() ?: 0\n'
    '            if (updatedCenterCount > 0) {\n'
    '                shippingDao.getAllCentersFlow().first()\n'
    '                    .filter { it.governorateId == gov.name }\n'
    '                    .forEach { center -> shippingDao.insertCenter(center.copy(deliveryPrice = gov.deliveryPrice)) }\n'
    '            }\n'
    '            Result.success(gov)'
)
if old_local not in repo_text:
    raise SystemExit('Governorate local-cache anchor not found')
repo_text = repo_text.replace(old_local, new_local, 1)
repo_path.write_text(repo_text, encoding='utf-8')


dao_path = root / 'app/src/main/java/com/pinky/dashboard/data/local/dao/Daos.kt'
dao_text = dao_path.read_text(encoding='utf-8')
if 'suspend fun deleteOrderItems(orderId: String)' not in dao_text:
    dao_needle = 'suspend fun getOrderItems(orderId: String): List<OrderItemEntity>'
    dao_index = dao_text.find(dao_needle)
    if dao_index < 0:
        raise SystemExit('OrderDao getOrderItems method not found')
    dao_end = dao_index + len(dao_needle)
    dao_text = dao_text[:dao_end] + """
    
    @Query("DELETE FROM order_items WHERE orderId = :orderId")
    suspend fun deleteOrderItems(orderId: String)
""" + dao_text[dao_end:]
    dao_path.write_text(dao_text, encoding='utf-8')

repo_text = repo_path.read_text(encoding='utf-8')
sync_insert_anchor = 'orderDao.insertOrders(orderEntities)'
sync_insert_index = repo_text.find(sync_insert_anchor, repo_text.index('override suspend fun syncOrders()'))
if sync_insert_index < 0:
    raise SystemExit('Order sync insert anchor not found')
after_insert = sync_insert_index + len(sync_insert_anchor)
if 'deleteOrderItems(dto.id)' not in repo_text:
    repo_text = repo_text[:after_insert] + """
                orders.filter { it.items != null }.forEach { dto -> orderDao.deleteOrderItems(dto.id) }
""" + repo_text[after_insert:]
repo_path.write_text(repo_text, encoding='utf-8')

# Prevent invalid/empty prices from silently falling back to unrelated default values.
shipping_screen = 'app/src/main/java/com/pinky/dashboard/ui/screens/shipping/ShippingScreen.kt'
shipping_path = root / shipping_screen
shipping_text = shipping_path.read_text(encoding='utf-8')
shipping_text = shipping_text.replace(
    '    var isActive by remember { mutableStateOf(gov.isActive) }\n',
    '    var isActive by remember { mutableStateOf(gov.isActive) }\n'
    '    var validationError by remember { mutableStateOf<String?>(null) }\n',
    1
)
shipping_text = shipping_text.replace(
    '                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)\n'
    '                )\n\n'
    '                OutlinedTextField(\n'
    '                    value = daysText,',
    '                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)\n'
    '                )\n'
    '                validationError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }\n\n'
    '                OutlinedTextField(\n'
    '                    value = daysText,',
    1
)
shipping_text = shipping_text.replace(
    '                            val price = priceText.toDoubleOrNull() ?: 60.0\n'
    '                            onSave(gov.copy(name = name, deliveryPrice = price, estimatedDays = daysText, isActive = isActive))',
    '                            val price = priceText.trim().toDoubleOrNull()\n'
    '                            if (name.isBlank() || price == null || price < 0.0) {\n'
    '                                validationError = "أدخل اسم المحافظة وسعر شحن صحيحًا (صفر أو أكثر)."\n'
    '                            } else {\n'
    '                                validationError = null\n'
    '                                onSave(gov.copy(name = name.trim(), deliveryPrice = price, estimatedDays = daysText, isActive = isActive))\n'
    '                            }',
    1
)
shipping_text = shipping_text.replace(
    '    var isActive by remember { mutableStateOf(center.isActive) }\n',
    '    var isActive by remember { mutableStateOf(center.isActive) }\n'
    '    var validationError by remember { mutableStateOf<String?>(null) }\n',
    1
)
shipping_text = shipping_text.replace(
    '                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)\n'
    '                )\n\n'
    '                OutlinedTextField(\n'
    '                    value = contact,',
    '                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)\n'
    '                )\n'
    '                validationError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }\n\n'
    '                OutlinedTextField(\n'
    '                    value = contact,',
    1
)
shipping_text = shipping_text.replace(
    '                            val price = priceText.toDoubleOrNull() ?: center.deliveryPrice\n'
    '                            onSave(center.copy(name = name, deliveryPrice = price, contactNumber = contact.ifBlank { null }, isActive = isActive))',
    '                            val price = priceText.trim().toDoubleOrNull()\n'
    '                            if (name.isBlank() || price == null || price < 0.0) {\n'
    '                                validationError = "أدخل اسم المركز وسعر توصيل صحيحًا (صفر أو أكثر)."\n'
    '                            } else {\n'
    '                                validationError = null\n'
    '                                onSave(center.copy(name = name.trim(), deliveryPrice = price, contactNumber = contact.ifBlank { null }, isActive = isActive))\n'
    '                            }',
    1
)
shipping_path.write_text(shipping_text, encoding='utf-8')

# Focused source diagnostics for order rendering, shipping writes, and owner permissions.
for source_file in root.rglob('*.kt'):
    if any(part in ('.gradle', 'build') for part in source_file.parts):
        continue
    relative = str(source_file.relative_to(root))
    lower_path = relative.lower()
    try:
        lines = source_file.read_text(encoding='utf-8').splitlines()
    except Exception:
        continue
    if any(token in lower_path for token in ('order', 'shipping', 'auth', 'staff', 'permission')):
        print(f'SOURCE_FILE {relative} ({len(lines)} lines)')
    if source_file.name == 'Order.kt' or ('order' in lower_path and any(token in lower_path for token in ('screen', 'dialog', 'detail', 'repository'))):
        print(f'SOURCE_EXCERPT_BEGIN {relative}')
        for line_no, line in enumerate(lines[:240], 1):
            print(f'  {line_no}: {line[:260]}')
        print(f'SOURCE_EXCERPT_END {relative}')
    if source_file.name in ('RepositoriesImpl.kt', 'SupabaseClient.kt', 'AuthModels.kt') or 'shipping' in lower_path:
        matches = [i for i, line in enumerate(lines)
                   if any(term in line.lower() for term in (
                       'admin_list_orders', 'admin_save_shipping', 'admin_apply_shipping',
                       'from("orders")', "from('orders')", 'orderitem', 'wholesale',
                       'product_id', 'productid', 'permissions', 'isowner', 'role ==',
                       'shipping_governorates', 'shipping_centers'
                   ))]
        if matches:
            print(f'SOURCE_MATCHES_BEGIN {relative}')
            emitted = set()
            for idx in matches[:35]:
                lo, hi = max(0, idx - 5), min(len(lines), idx + 7)
                for n in range(lo, hi):
                    if n not in emitted:
                        print(f'  {n+1}: {lines[n][:260]}')
                        emitted.add(n)
            print(f'SOURCE_MATCHES_END {relative}')


# Detailed snippets for the known order JSON schema mismatch and shipping editor path.
for relative, ranges in {
    'app/src/main/java/com/pinky/dashboard/data/local/entity/Entities.kt': [(1, 125)],
    'app/src/main/java/com/pinky/dashboard/domain/model/Order.kt': [(40, 90)],
    'app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt': [(80, 125), (425, 455)],
    'app/src/main/java/com/pinky/dashboard/ui/screens/shipping/ShippingScreen.kt': [(1, 180), (300, 520), (520, 703)],
    'app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrderDetailDialog.kt': [(1, 60), (180, 260), (410, 520)],
    'app/src/main/java/com/pinky/dashboard/ui/screens/orders/OrdersScreen.kt': [(1, 60), (100, 260)],
    'app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt': [(45, 225), (890, 970), (1390, 1455)],
    'app/src/main/java/com/pinky/dashboard/core/sync/OrderSyncManager.kt': [(1, 90)],
    'app/src/main/java/com/pinky/dashboard/domain/model/AuthModels.kt': [(1, 80)],
    'app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt': [(80, 125), (340, 455)],
    'app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt': [(1, 80), (405, 435)],
    'app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt': [(180, 240), (1145, 1185)],
    'app/src/main/java/com/pinky/dashboard/data/local/PinkyDatabase.kt': [(1, 70)]
}.items():
    target = root / relative
    if not target.exists():
        continue
    lines = target.read_text(encoding='utf-8').splitlines()
    print(f'DETAILED_SOURCE_BEGIN {relative}')
    for lo, hi in ranges:
        print(f'  RANGE {lo}-{hi}')
        for line_no in range(lo, min(hi, len(lines)) + 1):
            print(f'  {line_no}: {lines[line_no-1][:240]}')
    print(f'DETAILED_SOURCE_END {relative}')


# Trace the real call sites for order details and shipping persistence.
for source_file in root.rglob('*.kt'):
    if any(part in ('.gradle', 'build') for part in source_file.parts):
        continue
    try:
        lines = source_file.read_text(encoding='utf-8').splitlines()
    except Exception:
        continue
    terms = ('OrderDetailDialog(', 'upsertGovernorate(', 'upsertShippingCenter(',
             'saveGovernorate(', 'saveShippingCenter(', 'getGovernorates(',
             'getShippingCenters(', 'getOrders(', 'syncOrders(', 'getOrderItems(')
    hits = [i for i, line in enumerate(lines) if any(term in line for term in terms)]
    if hits:
        print(f'CALLSITE_MATCHES_BEGIN {source_file.relative_to(root)}')
        emitted = set()
        for idx in hits[:25]:
            for n in range(max(0, idx-5), min(len(lines), idx+8)):
                if n not in emitted:
                    print(f'  {n+1}: {lines[n][:240]}')
                    emitted.add(n)
        print(f'CALLSITE_MATCHES_END {source_file.relative_to(root)}')

print('Android CMS patches applied.')

# Full-bleed hero campaigns: add optional media fields without changing legacy slides.
hero_model = root / Path('app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt')
hero_model_text = hero_model.read_text(encoding='utf-8')
hero_class_start = hero_model_text.find("data class HeroSlideConfig(")
if hero_class_start < 0:
    raise SystemExit("HeroSlideConfig model was not found in the dashboard source")
hero_class_end = hero_model_text.find("\n)", hero_class_start)
if hero_class_end < 0:
    raise SystemExit("HeroSlideConfig model closing parenthesis was not found")
hero_class_end += 2
hero_class = hero_model_text[hero_class_start:hero_class_end]
hero_fields = [
    ('fullBleed', '    @Json(name = "fullBleed") val fullBleed: Boolean = false,'),
    ('mediaType', '    @Json(name = "mediaType") val mediaType: String = "image",'),
    ('mediaUrl', '    @Json(name = "mediaUrl") val mediaUrl: String = "",'),
    ('mobileMediaUrl', '    @Json(name = "mobileMediaUrl") val mobileMediaUrl: String = "",'),
    ('posterUrl', '    @Json(name = "posterUrl") val posterUrl: String = "",'),
    ('buttonVisible', '    @Json(name = "buttonVisible") val buttonVisible: Boolean = false,'),
    ('buttonPosition', '    @Json(name = "buttonPosition") val buttonPosition: String = "bottom-center",'),
    ('actionType', '    @Json(name = "actionType") val actionType: String = "url",'),
    ('productId', '    @Json(name = "productId") val productId: String = ""')
]
missing_fields = [line for field, line in hero_fields if '@Json(name = "' + field + '")' not in hero_class]
if missing_fields:
    hero_body = hero_class[:-2].rstrip()
    if not hero_body.endswith(","):
        hero_body += ","
    hero_class = hero_body + "\n" + "\n".join(missing_fields) + "\n)"
    hero_model_text = hero_model_text[:hero_class_start] + hero_class + hero_model_text[hero_class_end:]
hero_model.write_text(hero_model_text, encoding='utf-8')

hero_editor = root / Path('app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt')
hero_editor_text = hero_editor.read_text(encoding='utf-8')
for old_import, new_import in [
    ('import android.net.Uri\n', 'import android.content.ClipData\nimport android.content.ClipboardManager\nimport android.content.Context\nimport android.net.Uri\n'),
    ('import com.pinky.dashboard.data.remote.SupabaseStorageUploader\n',
     'import com.pinky.dashboard.data.remote.SupabaseStorageUploader\nimport com.pinky.dashboard.data.remote.HeroAdMediaUploader\n')
]:
    if old_import not in hero_editor_text:
        raise SystemExit('Missing WebsiteEditorScreen import anchor: ' + old_import.strip())
    if new_import not in hero_editor_text:
        hero_editor_text = hero_editor_text.replace(old_import, new_import, 1)

hero_start = hero_editor_text.index('@Composable\nfun HeroBannersForm(')
hero_end = hero_editor_text.index('\n@Composable\nfun CategoriesLayoutForm', hero_start)

hero_editor_block = r"""
@Composable
fun HeroCampaignMediaSelector(
    label: String,
    mediaUrl: String,
    onUrlChanged: (String) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var isUploading by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    var uploadSuccess by remember { mutableStateOf(false) }

    val picker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia()
    ) { uri: Uri? ->
        if (uri != null && !isUploading) {
            isUploading = true
            uploadError = null
            uploadSuccess = false
            scope.launch {
                try {
                    val publicUrl = HeroAdMediaUploader.upload(
                        contentResolver = context.contentResolver,
                        uri = uri,
                        isVideo = false
                    )
                    onUrlChanged(publicUrl)
                    uploadSuccess = true
                } catch (error: Exception) {
                    uploadError = error.message ?: "تعذر رفع صورة الإعلان. تحقق من الاتصال وصلاحية إدارة الموقع."
                    android.util.Log.e("EloryHeroCampaign", "Hero image upload failed", error)
                } finally {
                    isUploading = false
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, fontWeight = FontWeight.SemiBold)
        if (mediaUrl.isNotBlank()) {
            AsyncImage(
                model = mediaUrl,
                contentDescription = "معاينة صورة الهيرو",
                modifier = Modifier.fillMaxWidth().height(155.dp).clip(RoundedCornerShape(10.dp)),
                contentScale = ContentScale.Fit
            )
        } else {
            Box(
                modifier = Modifier.fillMaxWidth().height(105.dp).clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant),
                contentAlignment = Alignment.Center
            ) {
                Text("لم يتم رفع صورة لهذا الإعلان بعد", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                enabled = !isUploading,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
            ) {
                if (isUploading) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(7.dp))
                    Text("جاري الرفع...")
                } else {
                    Text(if (mediaUrl.isBlank()) "رفع صورة الإعلان" else "تغيير صورة الإعلان")
                }
            }
            if (mediaUrl.isNotBlank()) {
                OutlinedButton(onClick = { onUrlChanged(""); uploadSuccess = false }, enabled = !isUploading) {
                    Text("إزالة الصورة")
                }
            }
        }
        if (uploadSuccess) Text("تم رفع الصورة بنجاح", color = Color(0xFF16834A), style = MaterialTheme.typography.bodySmall)
        uploadError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        Text(
            "الصورة الواحدة تُستخدم على الكمبيوتر والموبايل. صمّم النصوص داخل الصورة نفسها؛ لن يضيف المتجر نصوصًا فوقها.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun HeroBannersForm(
    config: WebsiteConfig,
    onUpdate: (WebsiteConfig) -> Unit
) {
    val slides = config.heroSlides.sortedBy { it.sortOrder }
    fun updateSlide(
        slideId: String,
        activateUploadedSlideIfOnlyActiveIsEmpty: Boolean = false,
        transform: (HeroSlideConfig) -> HeroSlideConfig
    ) {
        // If the only active campaign has no image and the user uploads one
        // to another campaign, transfer the active slot to the image-bearing
        // campaign. Do not change multi-slide campaigns or valid active slides.
        val onlyActiveEmptySlide = slides.filter { it.isActive }.singleOrNull()
            ?.takeIf { active ->
                active.id != slideId &&
                    active.mediaUrl.ifBlank { active.imageUrl.ifBlank { active.mobileMediaUrl } }.isBlank()
            }
        val transferActivation = activateUploadedSlideIfOnlyActiveIsEmpty && onlyActiveEmptySlide != null
        val updatedSlides = slides.map { current ->
            when {
                current.id == slideId -> {
                    val changed = transform(current)
                    if (transferActivation) changed.copy(isActive = true) else changed
                }
                transferActivation && current.id == onlyActiveEmptySlide?.id -> current.copy(isActive = false)
                else -> current
            }
        }
        onUpdate(config.copy(heroSlides = updatedSlides))
    }

    val buttonPositions = listOf(
        listOf("top-left" to "أعلى يسار", "top-center" to "أعلى وسط", "top-right" to "أعلى يمين"),
        listOf("center-left" to "وسط يسار", "center" to "منتصف", "center-right" to "وسط يمين"),
        listOf("bottom-left" to "أسفل يسار", "bottom-center" to "أسفل وسط", "bottom-right" to "أسفل يمين")
    )

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text("إعلانات الهيرو", fontWeight = FontWeight.Bold, fontSize = 17.sp)
        Text(
            "ارفع تصميم البانر كاملًا. يمكنك إخفاء الزر وجعل الصورة كلها قابلة للضغط، أو إظهار زر واختيار مكانه.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        slides.forEachIndexed { index, slide ->
            val currentImage = slide.mediaUrl.ifBlank { slide.imageUrl.ifBlank { slide.mobileMediaUrl } }
            Card(
                modifier = Modifier.fillMaxWidth(),
                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("الإعلان " + (index + 1), fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Switch(
                            checked = slide.isActive,
                            onCheckedChange = { active -> updateSlide(slide.id) { it.copy(isActive = active) } }
                        )
                        IconButton(enabled = index > 0, onClick = {
                            val mutable = slides.toMutableList()
                            val item = mutable.removeAt(index)
                            mutable.add(index - 1, item)
                            onUpdate(config.copy(heroSlides = mutable.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.ArrowUpward, contentDescription = "تحريك لأعلى") }
                        IconButton(enabled = index < slides.lastIndex, onClick = {
                            val mutable = slides.toMutableList()
                            val item = mutable.removeAt(index)
                            mutable.add(index + 1, item)
                            onUpdate(config.copy(heroSlides = mutable.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.ArrowDownward, contentDescription = "تحريك لأسفل") }
                        IconButton(onClick = {
                            onUpdate(config.copy(heroSlides = slides.filterNot { it.id == slide.id }.mapIndexed { i, v -> v.copy(sortOrder = i + 1) }))
                        }) { Icon(Icons.Filled.Delete, contentDescription = "حذف الإعلان", tint = MaterialTheme.colorScheme.error) }
                    }

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            if (slide.isActive) "الحالة: الإعلان ظاهر على الموقع"
                            else "الحالة: الإعلان مخفي عن الزوار",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                            color = if (slide.isActive) Color(0xFF16834A) else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        if (!slide.isActive && currentImage.isNotBlank()) {
                            Spacer(Modifier.width(8.dp))
                            Text("الصورة محفوظة لكن الإعلان متوقف", style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.error)
                        }
                    }
                    if (slide.isActive && currentImage.isBlank()) {
                        Text(
                            "تنبيه: هذا الإعلان نشط لكنه بلا صورة، لذلك لن يظهر تصميمه الجديد على الموقع.",
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall
                        )
                    }

                    HeroCampaignMediaSelector(
                        label = "صورة البانر",
                        mediaUrl = currentImage,
                        onUrlChanged = { url ->
                            updateSlide(slide.id, activateUploadedSlideIfOnlyActiveIsEmpty = true) {
                                it.copy(
                                    fullBleed = true,
                                    mediaType = "image",
                                    mediaUrl = url,
                                    imageUrl = url,
                                    mobileMediaUrl = "",
                                    posterUrl = ""
                                )
                            }
                        }
                    )

                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("إظهار زر فوق الصورة", fontWeight = FontWeight.SemiBold)
                            Text("أوقفه لجعل الصورة كلها هي الرابط بدون زر ظاهر.", style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Switch(
                            checked = slide.buttonVisible,
                            onCheckedChange = { visible -> updateSlide(slide.id) { it.copy(buttonVisible = visible) } }
                        )
                    }

                    if (slide.buttonVisible) {
                        OutlinedTextField(
                            value = slide.buttonText,
                            onValueChange = { value -> updateSlide(slide.id) { it.copy(buttonText = value) } },
                            label = { Text("النص الذي يظهر على الزر") },
                            placeholder = { Text("اكتشفي المنتج") },
                            modifier = Modifier.fillMaxWidth(),
                            singleLine = true
                        )
                        Text("مكان الزر داخل الصورة", fontWeight = FontWeight.SemiBold)
                        buttonPositions.forEach { positionRow ->
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                positionRow.forEach { (position, label) ->
                                    if (slide.buttonPosition == position) {
                                        Button(
                                            onClick = { updateSlide(slide.id) { it.copy(buttonPosition = position) } },
                                            modifier = Modifier.weight(1f),
                                            colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
                                        ) { Text(label, maxLines = 1) }
                                    } else {
                                        OutlinedButton(
                                            onClick = { updateSlide(slide.id) { it.copy(buttonPosition = position) } },
                                            modifier = Modifier.weight(1f)
                                        ) { Text(label, maxLines = 1) }
                                    }
                                }
                            }
                        }
                    }

                    Text("ماذا يحدث عند الضغط على الصورة أو الزر؟", fontWeight = FontWeight.SemiBold)
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("product" to "صفحة منتج", "url" to "رابط خارجي", "none" to "بدون إجراء").forEach { (type, label) ->
                            if (slide.actionType == type) {
                                Button(
                                    onClick = { updateSlide(slide.id) { it.copy(actionType = type) } },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
                                ) { Text(label, maxLines = 1) }
                            } else {
                                OutlinedButton(
                                    onClick = { updateSlide(slide.id) { it.copy(actionType = type) } },
                                    modifier = Modifier.weight(1f)
                                ) { Text(label, maxLines = 1) }
                            }
                        }
                    }

                    when (slide.actionType) {
                        "product" -> {
                            OutlinedTextField(
                                value = slide.productId,
                                onValueChange = { value -> updateSlide(slide.id) { it.copy(productId = value.trim()) } },
                                label = { Text("معرّف المنتج") },
                                placeholder = { Text("الصقي معرّف المنتج هنا") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                            Text(
                                "الأفضل اختيار صفحة المنتج: سيفتح تفاصيله ليختار العميل اللون والمقاس ثم يضيفه إلى السلة.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            if (slide.productId.isBlank()) {
                                Text("أضيفي معرّف المنتج حتى يعمل الضغط على الإعلان.", color = MaterialTheme.colorScheme.error,
                                    style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        "url" -> {
                            OutlinedTextField(
                                value = slide.actionUrl,
                                onValueChange = { value -> updateSlide(slide.id) { it.copy(actionUrl = value) } },
                                label = { Text("الرابط الذي يفتحه الإعلان") },
                                placeholder = { Text("https://...") },
                                modifier = Modifier.fillMaxWidth(),
                                singleLine = true
                            )
                        }
                        else -> {
                            Text(
                                "الضغط على الصورة لن ينفذ أي إجراء.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    if (currentImage.isBlank()) {
                        Text("ارفع صورة البانر قبل تفعيل هذا الإعلان.", color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        Button(
            onClick = {
                val updated = slides + HeroSlideConfig(
                    id = "hero_" + System.currentTimeMillis(),
                    imageUrl = "",
                    smallText = "",
                    title = "",
                    arabicTitle = "",
                    description = "",
                    buttonText = "اكتشفي المنتج",
                    actionUrl = "",
                    sortOrder = slides.size + 1,
                    isActive = true,
                    fullBleed = true,
                    mediaType = "image",
                    mediaUrl = "",
                    mobileMediaUrl = "",
                    posterUrl = "",
                    buttonVisible = false,
                    buttonPosition = "bottom-center",
                    actionType = "product",
                    productId = ""
                )
                onUpdate(config.copy(heroSlides = updated))
            },
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = PinkPrimary, contentColor = Color(0xFF381528))
        ) { Icon(Icons.Filled.Add, contentDescription = null); Spacer(Modifier.width(6.dp)); Text("إضافة إعلان هيرو") }
    }
}
"""
hero_editor_text = hero_editor_text[:hero_start] + hero_editor_block + hero_editor_text[hero_end:]
hero_editor.write_text(hero_editor_text, encoding='utf-8')

# Authenticated upload helper for dedicated image/video campaign assets.
uploader_file = root / Path('app/src/main/java/com/pinky/dashboard/data/remote/HeroAdMediaUploader.kt')
uploader_file.parent.mkdir(parents=True, exist_ok=True)
uploader_file.write_text(r"""package com.pinky.dashboard.data.remote

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody
import okio.BufferedSink
import okio.source
import java.io.IOException
import java.util.UUID

object HeroAdMediaUploader {
    private const val BUCKET = "hero-ads"
    private const val MAX_IMAGE_BYTES = 15L * 1024L * 1024L
    private const val MAX_VIDEO_BYTES = 50L * 1024L * 1024L

    suspend fun upload(
        contentResolver: ContentResolver,
        uri: Uri,
        isVideo: Boolean
    ): String = withContext(Dispatchers.IO) {
        val mimeType = contentResolver.getType(uri)?.lowercase()
            ?: throw IllegalArgumentException("تعذر تحديد نوع الملف. اختر صورة أو فيديو بصيغة مدعومة.")

        val extension = when (mimeType) {
            "image/jpeg" -> "jpg"
            "image/png" -> "png"
            "image/webp" -> "webp"
            "image/avif" -> "avif"
            "video/mp4" -> "mp4"
            "video/webm" -> "webm"
            else -> throw IllegalArgumentException(
                if (isVideo) "صيغة الفيديو غير مدعومة. استخدم MP4 أو WebM."
                else "صيغة الصورة غير مدعومة. استخدم JPG أو PNG أو WebP أو AVIF."
            )
        }
        if (isVideo != mimeType.startsWith("video/")) {
            throw IllegalArgumentException("نوع الملف لا يطابق نوع الوسائط المختار.")
        }

        val maxBytes = if (isVideo) MAX_VIDEO_BYTES else MAX_IMAGE_BYTES
        val queriedLength = contentResolver.query(
            uri, arrayOf(OpenableColumns.SIZE), null, null, null
        )?.use { cursor ->
            val index = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (index >= 0 && cursor.moveToFirst()) cursor.getLong(index) else -1L
        } ?: -1L
        val length = if (queriedLength > 0L) queriedLength else {
            contentResolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L
        }

        if (length <= 0L || length > maxBytes) {
            throw IllegalArgumentException(
                if (isVideo) "حجم الفيديو يجب ألا يتجاوز 50 ميجابايت."
                else "حجم الصورة يجب ألا يتجاوز 15 ميجابايت."
            )
        }

        val fileName = "hero-" + UUID.randomUUID().toString() + "." + extension
        val body = object : RequestBody() {
            override fun contentType() = mimeType.toMediaTypeOrNull()
            override fun contentLength() = length
            override fun writeTo(sink: BufferedSink) {
                val input = contentResolver.openInputStream(uri)
                    ?: throw IOException("تعذر قراءة الملف المحدد.")
                input.use { stream ->
                    stream.source().use { source -> sink.writeAll(source) }
                }
            }
        }

        val response = SupabaseClient.service.uploadStorageFile(
            bucket = BUCKET,
            path = fileName,
            file = body,
            contentType = mimeType
        )
        if (!response.isSuccessful) {
            val details = response.errorBody()?.string()?.take(300).orEmpty()
            throw IOException("فشل رفع الإعلان إلى التخزين (" + response.code() + "). " + details)
        }

        SupabaseClient.supabaseUrl.trimEnd('/') +
            "/storage/v1/object/public/" + BUCKET + "/" + fileName
    }
}
""", encoding='utf-8')

print('Hero campaign media controls and uploader generated.')
