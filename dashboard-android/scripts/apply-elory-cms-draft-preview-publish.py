import os
from pathlib import Path
root = Path(os.environ["PROJECT_DIR"])
def read(rel):
    p=root/rel
    if not p.is_file(): raise SystemExit("Missing "+rel)
    return p,p.read_text(encoding="utf-8")
def once(s,a,b,label):
    if s.count(a)!=1: raise SystemExit(label+" anchor count "+str(s.count(a)))
    return s.replace(a,b,1)

model_path, model_text = read("app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt")
if "data class SiteCustomizationDraftRequest(" not in model_text:
    model_text += '''

@JsonClass(generateAdapter = true)
data class SiteCustomizationDraftRequest(
    @Json(name = "p_config") val config: SiteCustomizationConfig
)
'''
    model_path.write_text(model_text, encoding="utf-8")

p,s=read("app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt")
if "import retrofit2.http.POST" not in s:
    s=s.replace("import retrofit2.http.PUT\n","import retrofit2.http.PUT\nimport retrofit2.http.POST\n",1)
if "fun saveSiteCustomizationDraft(" not in s:
    st=s.find("interface SupabaseService"); br=s.find("{",st); depth=0; en=-1
    if st<0 or br<0: raise SystemExit("SupabaseService missing")
    for i in range(br,len(s)):
        if s[i]=="{": depth+=1
        elif s[i]=="}":
            depth-=1
            if depth==0: en=i; break
    if en<0: raise SystemExit("SupabaseService end missing")
    s=s[:en]+'''
    @POST("rest/v1/rpc/admin_save_site_customization_draft")
    suspend fun saveSiteCustomizationDraft(@Body params: com.pinky.dashboard.domain.model.SiteCustomizationDraftRequest): Response<Boolean>

    @POST("rest/v1/rpc/admin_get_site_customization_draft")
    suspend fun getSiteCustomizationDraft(@Body params: Map<String, Any>): Response<com.pinky.dashboard.domain.model.SiteCustomizationConfig>

    @POST("rest/v1/rpc/admin_clear_site_customization_draft")
    suspend fun clearSiteCustomizationDraft(@Body params: Map<String, Any>): Response<Boolean>
'''+s[en:]
p.write_text(s,encoding="utf-8")

p,s=read("app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt")
if "private fun buildWebsiteSiteConfig" not in s:
    a=s.find("                val siteConfigObj = SiteCustomizationConfig(")
    b=s.find("\n\n                val customizationsDto =",a)
    if a<0 or b<0: raise SystemExit("SiteCustomizationConfig mapping missing")
    mapping=s[a:b]
    helper="    private fun buildWebsiteSiteConfig(config: WebsiteConfig): SiteCustomizationConfig {\n"+"\n".join("    "+x for x in mapping.splitlines())+"\n        return siteConfigObj\n    }\n\n"
    at=s.find("    fun updateWebsiteConfig(config: WebsiteConfig)")
    if at<0: raise SystemExit("updateWebsiteConfig missing")
    s=s[:at]+helper+s[at:]
    a=s.find("                val siteConfigObj = SiteCustomizationConfig(",at+len(helper))
    b=s.find("\n\n                val customizationsDto =",a)
    if a<0 or b<0: raise SystemExit("mapping refind failed")
    s=s[:a]+"                val siteConfigObj = buildWebsiteSiteConfig(config)"+s[b:]
# Load the saved CMS draft before the published config, so it survives app restarts.
import re
cfg_matches = list(re.finditer(r'(?m)^(\s*)val cfgObj\s*=', s))
if len(cfg_matches) == 1 and "getSiteCustomizationDraft" not in s:
    match = cfg_matches[0]
    indent = match.group(1)
    prelude = (
        indent + "val draftConfig: com.pinky.dashboard.domain.model.SiteCustomizationConfig? = try {\n" +
        indent + "    val draftResponse = SupabaseClient.service.getSiteCustomizationDraft(emptyMap())\n" +
        indent + "    if (draftResponse.isSuccessful) draftResponse.body() else null\n" +
        indent + "} catch (_: Exception) { null }\n"
    )
    s = s[:match.start()] + prelude + s[match.start():]
    s = re.sub(r'(?m)^(\s*)val cfgObj\s*=', r'\1val cfgObj = draftConfig ?: ', s, count=1)
elif "getSiteCustomizationDraft" not in s:
    raise SystemExit("Could not uniquely locate CMS config loader for saved draft restoration")

state='''    private val _websiteConfig = MutableStateFlow(WebsiteConfig())
    val websiteConfig: StateFlow<WebsiteConfig> = _websiteConfig.asStateFlow()'''
if state in s and "_websiteDraftSaveState" not in s:
    s=once(s,state,state+'''
    private val _websiteDraftSaveState = MutableStateFlow("idle")
    val websiteDraftSaveState: StateFlow<String> = _websiteDraftSaveState.asStateFlow()''',"draft state")
if "fun saveWebsiteDraft(config: WebsiteConfig)" not in s:
    method='''
    fun saveWebsiteDraft(config: WebsiteConfig) {
        viewModelScope.launch {
            _websiteDraftSaveState.value = "saving"
            try {
                val siteConfigObj = buildWebsiteSiteConfig(config)
                val response = SupabaseClient.service.saveSiteCustomizationDraft(com.pinky.dashboard.domain.model.SiteCustomizationDraftRequest(siteConfigObj))
                if (!response.isSuccessful) {
                    android.util.Log.e("EloryWebsite", "Draft save failed: " + response.code())
                    _websiteDraftSaveState.value = "error"
                    return@launch
                }
                _websiteConfig.value = config
                _websiteDraftSaveState.value = "success"
            } catch (e: Exception) {
                android.util.Log.e("EloryWebsite", "Draft save failed", e)
                _websiteDraftSaveState.value = "error"
            }
        }
    }

'''
    at=s.find("    fun updateWebsiteConfig(config: WebsiteConfig)")
    if at<0: raise SystemExit("draft method insertion point missing")
    s=s[:at]+method+s[at:]
a=s.find("    fun updateWebsiteConfig(config: WebsiteConfig)"); b=s.find("\n    // Notification management",a)
if a<0 or b<0: raise SystemExit("publish method missing")
pub=s[a:b]
if "saveSiteCustomizationDraft" not in pub:
    pub=once(pub,
'''                val settingsResponse = SupabaseClient.service.upsertStoreSettings(settingsDto)
                val customizationsResponse = SupabaseClient.service.upsertSiteCustomizations(customizationsDto)''',
'''                val draftResponse = SupabaseClient.service.saveSiteCustomizationDraft(com.pinky.dashboard.domain.model.SiteCustomizationDraftRequest(siteConfigObj))
                if (!draftResponse.isSuccessful) {
                    android.util.Log.e("EloryWebsite", "Publish checkpoint failed: " + draftResponse.code())
                    return@launch
                }
                val settingsResponse = SupabaseClient.service.upsertStoreSettings(settingsDto)
                val customizationsResponse = SupabaseClient.service.upsertSiteCustomizations(customizationsDto)''',"publish checkpoint")
    pub=once(pub,"                _websiteConfig.value = config",'''
                val clearDraftResponse = SupabaseClient.service.clearSiteCustomizationDraft(emptyMap())
                if (!clearDraftResponse.isSuccessful) {
                    android.util.Log.w("EloryWebsite", "Published, but draft cleanup failed: " + clearDraftResponse.code())
                }
                _websiteConfig.value = config''',"clear draft")
    s=s[:a]+pub+s[b:]
p.write_text(s,encoding="utf-8")

p,s=read("app/src/main/java/com/pinky/dashboard/ui/PinkyApp.kt")
if "websiteDraftSaveState" not in s:
    s=once(s,"    val websiteSaveState by viewModel.websiteSaveState.collectAsStateWithLifecycle()",
        "    val websiteSaveState by viewModel.websiteSaveState.collectAsStateWithLifecycle()\n    val websiteDraftSaveState by viewModel.websiteDraftSaveState.collectAsStateWithLifecycle()","draft state collect")
if "onSaveDraft = { viewModel.saveWebsiteDraft(it) }" not in s:
    s=once(s,"                                    onSaveConfig = { viewModel.updateWebsiteConfig(it) },",
        "                                    onSaveConfig = { viewModel.updateWebsiteConfig(it) },\n                                    onSaveDraft = { viewModel.saveWebsiteDraft(it) },\n                                    draftSaveState = websiteDraftSaveState,","draft callback")
p.write_text(s,encoding="utf-8")

p,s=read("app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt")
s=s.replace("    saveState: String = \"idle\",\n    modifier: Modifier = Modifier",
    "    saveState: String = \"idle\",\n    onSaveDraft: (WebsiteConfig) -> Unit = {},\n    draftSaveState: String = \"idle\",\n    modifier: Modifier = Modifier",1)
s=s.replace("1-11 = section dialog index","1-12 = section dialog index",1)
card='''                    // Card 11: الإعدادات العامة والألوان
                    item {
                        SectionCard(
                            title = "إعدادات عامة وألوان وهوية الموقع",
                            description = "اسم المتجر، تفاصيل السيو والبحث، والخطوط ولون الهوية الأساسي",
                            icon = Icons.Outlined.SettingsSuggest,
                            isActive = true,
                            onToggleActive = null,
                            onClick = { activeEditingDialog = 11 }
                        )
                    }
'''
if "activeEditingDialog = 12" not in s:
    s=once(s,card,card+'''
                    item {
                        SectionCard(
                            title = "ترتيب وظهور أقسام الصفحة",
                            description = "إخفاء الأقسام وترتيبها وإنشاء أقسام مخصصة",
                            icon = Icons.Outlined.ViewList,
                            isActive = true,
                            onToggleActive = null,
                            onClick = { activeEditingDialog = 12 }
                        )
                    }
''',"sections card")
s=s.replace('                    11 -> "هوية وإعدادات الموقع العامة" to Icons.Outlined.SettingsSuggest\n                    else ->',
'                    11 -> "هوية وإعدادات الموقع العامة" to Icons.Outlined.SettingsSuggest\n                    12 -> "ترتيب وظهور أقسام الصفحة" to Icons.Outlined.ViewList\n                    else ->',1)
s=s.replace("                        11 -> GlobalSettingsForm(dialogConfig, onUpdate = { dialogConfig = it })",
"                        11 -> GlobalSettingsForm(dialogConfig, onUpdate = { dialogConfig = it })\n                        12 -> SectionsLayoutForm(dialogConfig, onUpdate = { dialogConfig = it })",1)
s=once(s,'''            onSaveConfig = { updated ->
                config = updated
                onSaveConfig(updated)
            },''','''            onSaveConfig = { updated ->
                config = updated
            },''',"local dialog apply")
if "حفظ مسودة" not in s:
    s=once(s,"            // Mode Tabs: Edit vs Live Preview Mockup",'''
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                OutlinedButton(onClick = { onSaveDraft(config) }, enabled = draftSaveState != "saving", modifier = Modifier.weight(1f)) {
                    Icon(Icons.Outlined.Save, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (draftSaveState == "saving") "جارٍ حفظ المسودة..." else "حفظ مسودة")
                }
                Text(
                    when (draftSaveState) {
                        "success" -> "المسودة محفوظة"
                        "error" -> "فشل حفظ المسودة"
                        else -> "التعديلات لا تظهر قبل النشر"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (draftSaveState == "error") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Mode Tabs: Edit vs Live Preview Mockup''',"draft row")
if "selectedPreviewDevice" not in s:
    s=once(s,"    var selectedTab by remember { mutableIntStateOf(0) } // 0 = Editor, 1 = Live Preview Mockup",
        "    var selectedTab by remember { mutableIntStateOf(0) } // 0 = Editor, 1 = Live Preview Mockup\n    var selectedPreviewDevice by remember { mutableIntStateOf(0) }","preview state")
old='''                // Live Mockup rendering
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(16.dp),
                    contentAlignment = Alignment.TopCenter
                ) {
                    PhoneMockupView(
                        config = config,
                        categories = categories,
                        banners = banners
                    )
                }'''
new='''                Column(Modifier.fillMaxSize().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (selectedPreviewDevice == 0) Button(onClick = { selectedPreviewDevice = 0 }) { Text("معاينة الموبايل") }
                        else OutlinedButton(onClick = { selectedPreviewDevice = 0 }) { Text("معاينة الموبايل") }
                        if (selectedPreviewDevice == 1) Button(onClick = { selectedPreviewDevice = 1 }) { Text("معاينة الكمبيوتر") }
                        else OutlinedButton(onClick = { selectedPreviewDevice = 1 }) { Text("معاينة الكمبيوتر") }
                    }
                    Spacer(Modifier.height(10.dp))
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.TopCenter) {
                        if (selectedPreviewDevice == 0) PhoneMockupView(config = config, categories = categories, banners = banners)
                        else DesktopMockupView(config = config, categories = categories, banners = banners)
                    }
                }'''
if old in s: s=once(s,old,new,"responsive preview")
elif "DesktopMockupView(config = config" not in s: raise SystemExit("phone preview block missing")
s=s.replace('text = { Text("حفظ ونشر التعديلات", fontWeight = FontWeight.Bold) }',
            'text = { Text("نشر التعديلات", fontWeight = FontWeight.Bold) }',1)
p.write_text(s,encoding="utf-8")

desktop=root/"app/src/main/java/com/pinky/dashboard/ui/screens/website/DesktopMockupView.kt"
desktop.write_text(r'''package com.pinky.dashboard.ui.screens.website

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
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

@Composable
fun DesktopMockupView(config: WebsiteConfig, categories: List<Category>, banners: List<Offer>) {
    val hero = config.heroSlides.firstOrNull { it.isActive }
    Card(Modifier.fillMaxWidth().fillMaxHeight(.96f), shape=RoundedCornerShape(14.dp),
        border=androidx.compose.foundation.BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant)) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().background(Color(0xFFF9F5F7)).padding(24.dp),
                verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.SpaceBetween) {
                Text(config.storeName,fontWeight=FontWeight.ExtraBold,fontSize=22.sp,color=Color(0xFF381528))
                Row(horizontalArrangement=Arrangement.spacedBy(18.dp)) {
                    Text("الرئيسية"); Text("الأقسام"); Text("المنتجات"); Text("تواصل معنا")
                }
                Text("♡   🛍",color=Color(0xFFC96F92))
            }
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(26.dp),
                verticalArrangement=Arrangement.spacedBy(18.dp)) {
                if(config.showAnnouncementBar) Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(Color(0xFF381528)).padding(9.dp),contentAlignment=Alignment.Center) {
                    Text(config.announcementMsg1,color=Color.White,fontSize=12.sp)
                }
                if(config.showHeroBanner && hero!=null) Row(Modifier.fillMaxWidth().heightIn(min=210.dp).clip(RoundedCornerShape(16.dp)).background(Color(0xFFFFF0F5)),verticalAlignment=Alignment.CenterVertically) {
                    Column(Modifier.weight(1f).padding(24.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                        Text(hero.smallText,color=Color(0xFF9D5574),fontWeight=FontWeight.Bold)
                        Text(hero.title,color=Color(0xFF381528),fontSize=28.sp,fontWeight=FontWeight.ExtraBold)
                        if(hero.arabicTitle.isNotBlank()) Text(hero.arabicTitle,color=Color(0xFF381528),fontSize=18.sp,fontWeight=FontWeight.Bold)
                        Text(hero.description,color=Color.DarkGray)
                        if(hero.buttonVisible) Text(hero.buttonText,color=Color(0xFFC96F92),fontWeight=FontWeight.Bold)
                    }
                    if(hero.imageUrl.isNotBlank()) AsyncImage(model=hero.mediaUrl.ifBlank{hero.imageUrl},contentDescription=null,
                        modifier=Modifier.weight(1.2f).fillMaxHeight(),contentScale=ContentScale.Crop)
                }
                if(config.categoriesIsVisible) Column(verticalArrangement=Arrangement.spacedBy(10.dp)) {
                    Text(config.categoriesTitle,fontSize=20.sp,fontWeight=FontWeight.Bold)
                    Row(horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                        categories.filter{it.isActive}.take(7).forEach { c ->
                            Column(Modifier.weight(1f),horizontalAlignment=Alignment.CenterHorizontally) {
                                if(c.imageUrl.isNotBlank()) AsyncImage(c.imageUrl,c.name,Modifier.size(70.dp).clip(RoundedCornerShape(35.dp)),contentScale=ContentScale.Crop)
                                else Box(Modifier.size(70.dp).clip(RoundedCornerShape(35.dp)).background(Color(0xFFF8E8EF)))
                                Text(c.name,fontSize=11.sp,textAlign=TextAlign.Center,maxLines=2)
                            }
                        }
                    }
                }
                Column(verticalArrangement=Arrangement.spacedBy(6.dp)) {
                    Text(config.productsSectionTitle,fontSize=20.sp,fontWeight=FontWeight.Bold)
                    Text(config.productsSectionSubtitle,color=Color.Gray,fontSize=12.sp)
                    if(banners.isNotEmpty()) Text("عروض متاحة: "+banners.size,color=Color(0xFFC96F92),fontSize=12.sp)
                }
                if(config.primeIsVisible) Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).background(Color(0xFF381528)).padding(18.dp)) {
                    Text(config.primeName,color=Color.White,fontWeight=FontWeight.Bold,fontSize=20.sp)
                    Text(config.primeDescription,color=Color.White.copy(alpha=.85f),fontSize=13.sp)
                }
                config.customSections.filter{it.isVisible}.sortedBy{it.sortOrder}.forEach { block ->
                    Column(Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp)).background(Color(0xFFFFF0F5)).padding(18.dp)) {
                        if(block.imageUrl.isNotBlank()) AsyncImage(block.imageUrl,null,Modifier.fillMaxWidth().height(170.dp).clip(RoundedCornerShape(10.dp)),contentScale=ContentScale.Crop)
                        Text(block.title,fontSize=18.sp,fontWeight=FontWeight.Bold)
                        Text(block.text,fontSize=13.sp)
                        if(block.buttonText.isNotBlank()) Text(block.buttonText,color=Color(0xFFC96F92),fontWeight=FontWeight.Bold)
                    }
                }
                Text("معاينة تقريبية لتخطيط الكمبيوتر",color=Color.Gray,fontSize=10.sp)
            }
        }
    }
}
''',encoding="utf-8")
print("CMS draft/publish and responsive preview patch applied.")


# 6) Give custom content sections first-class FAQ and trust layouts, and separate SEO title/description.
model_path = root / "app/src/main/java/com/pinky/dashboard/domain/model/WebsiteCustomizationConfig.kt"
model_text = model_path.read_text(encoding="utf-8")
custom_start = model_text.find("data class CustomSiteSectionConfig(")
if custom_start < 0:
    raise SystemExit("CustomSiteSectionConfig was not found")
custom_end = model_text.find("\n)", custom_start)
if custom_end < 0:
    raise SystemExit("CustomSiteSectionConfig closing parenthesis was not found")
custom_block = model_text[custom_start:custom_end+2]
if '@Json(name = "sectionType")' not in custom_block:
    custom_block = custom_block[:-2].rstrip()
    if not custom_block.endswith(","):
        custom_block += ","
    custom_block += '''
    @Json(name = "sectionType") val sectionType: String = "content",
    @Json(name = "faqItems") val faqItems: List<SiteFaqEntry> = emptyList(),
    @Json(name = "trustItems") val trustItems: List<SiteTrustEntry> = emptyList()
)'''
    model_text = model_text[:custom_start] + custom_block + model_text[custom_end+2:]
if "data class SiteFaqEntry(" not in model_text:
    model_text += '''

@JsonClass(generateAdapter = true)
data class SiteFaqEntry(
    @Json(name = "question") val question: String = "",
    @Json(name = "answer") val answer: String = ""
)

@JsonClass(generateAdapter = true)
data class SiteTrustEntry(
    @Json(name = "icon") val icon: String = "✓",
    @Json(name = "title") val title: String = "",
    @Json(name = "description") val description: String = ""
)
'''
model_path.write_text(model_text, encoding="utf-8")

store_model_path = root / "app/src/main/java/com/pinky/dashboard/domain/model/StoreModels.kt"
store_model_text = store_model_path.read_text(encoding="utf-8")
if "val metaTitle: String = \"\"" not in store_model_text:
    store_model_text = once(
        store_model_text,
        '    val storeName: String = "Elory Store",',
        '    val storeName: String = "Elory Store",\n    val metaTitle: String = "",\n    val metaDescription: String = "",',
        "independent SEO fields"
    )
store_model_path.write_text(store_model_text, encoding="utf-8")

vm_path = root / "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"
vm_text = vm_path.read_text(encoding="utf-8")
vm_text = vm_text.replace("metaTitle = config.storeName,", "metaTitle = config.metaTitle.ifBlank { config.storeName },", 1)
vm_text = vm_text.replace("metaDescription = config.aboutText,", "metaDescription = config.metaDescription.ifBlank { config.aboutText },", 1)
load_anchor = "                            isStoreOpen = cfgObj?.global?.isStoreOpen ?: currentConfig.isStoreOpen,"
if load_anchor in vm_text and "metaTitle = cfgObj?.global?.metaTitle" not in vm_text:
    vm_text = once(
        vm_text,
        load_anchor,
        load_anchor + '''
                            metaTitle = cfgObj?.global?.metaTitle ?: currentConfig.metaTitle,
                            metaDescription = cfgObj?.global?.metaDescription ?: currentConfig.metaDescription,''',
        "load separate SEO metadata"
    )
vm_path.write_text(vm_text, encoding="utf-8")

editor_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"
editor_text = editor_path.read_text(encoding="utf-8")
seo_title_old = '''            value = config.storeName, // Bind or use helper
            onValueChange = { onUpdate(config.copy(storeName = it)) },
            label = { Text("عنوان السيو الترويجي (Meta Title)") },'''
seo_title_new = '''            value = config.metaTitle,
            onValueChange = { onUpdate(config.copy(metaTitle = it)) },
            label = { Text("عنوان السيو (Meta Title)") },'''
if seo_title_old in editor_text:
    editor_text = once(editor_text, seo_title_old, seo_title_new, "independent SEO title editor")
seo_desc_old = '''            value = config.aboutText,
            onValueChange = { onUpdate(config.copy(aboutText = it)) },
            label = { Text("الوصف لمحركات البحث (Meta Description)") },'''
seo_desc_new = '''            value = config.metaDescription,
            onValueChange = { onUpdate(config.copy(metaDescription = it)) },
            label = { Text("الوصف لمحركات البحث (Meta Description)") },'''
if seo_desc_old in editor_text:
    editor_text = once(editor_text, seo_desc_old, seo_desc_new, "independent SEO description editor")

# The promo-center patch owns the hero editor range and can replace the adjacent CMS section editor.
# Reinsert the exact previously reviewed SectionsLayoutForm implementation after all other patches.
if "fun SectionsLayoutForm(" not in editor_text:
    cms_source = (Path(__file__).resolve().parent / "apply-elory-cms-patch.py").read_text(encoding="utf-8")
    layout_marker = "layout='''"
    layout_start = cms_source.find(layout_marker)
    layout_end = cms_source.find("'''", layout_start + len(layout_marker))
    if layout_start < 0 or layout_end < 0:
        raise SystemExit("Could not recover the existing SectionsLayoutForm source")
    layout_source = cms_source[layout_start + len(layout_marker):layout_end].strip("\n")
    category_anchor = "\n@Composable\nfun CategoriesLayoutForm"
    if category_anchor not in editor_text:
        raise SystemExit("Could not find insertion point for SectionsLayoutForm")
    editor_text = editor_text.replace(category_anchor, "\n" + layout_source + category_anchor, 1)

# The custom-section editor can switch between generic content, FAQ accordions and trust cards.
custom_title_field = '''                    OutlinedTextField(local.title, { local=local.copy(title=it) }, label={ Text("عنوان القسم") }, modifier=Modifier.fillMaxWidth())'''
editor_text = editor_text.replace(
        "الحفظ ينشر الإعدادات إلى الموقع.",
        "حفظ المسودة لا يغير الموقع؛ راجع المعاينة ثم اختر نشر التعديلات.",
        1
    )
if custom_title_field in editor_text and "اختيار نوع القسم" not in editor_text:
    section_type_controls = custom_title_field + '''
                    Text("نوع القسم", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("content" to "محتوى", "faq" to "أسئلة شائعة", "trust" to "عناصر ثقة").forEach { (kind, label) ->
                            if (local.sectionType == kind) {
                                Button(onClick = { local = local.copy(sectionType = kind) }, modifier = Modifier.weight(1f)) { Text(label) }
                            } else {
                                OutlinedButton(onClick = { local = local.copy(sectionType = kind) }, modifier = Modifier.weight(1f)) { Text(label) }
                            }
                        }
                    }
                    if (local.sectionType == "faq") {
                        Text("الأسئلة والأجوبة", fontWeight = FontWeight.SemiBold)
                        local.faqItems.forEachIndexed { index, entry ->
                            OutlinedTextField(
                                value = entry.question,
                                onValueChange = { value -> local = local.copy(faqItems = local.faqItems.mapIndexed { i, old -> if (i == index) old.copy(question = value) else old }) },
                                label = { Text("السؤال " + (index + 1)) },
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                value = entry.answer,
                                onValueChange = { value -> local = local.copy(faqItems = local.faqItems.mapIndexed { i, old -> if (i == index) old.copy(answer = value) else old }) },
                                label = { Text("الإجابة") },
                                modifier = Modifier.fillMaxWidth(),
                                minLines = 2
                            )
                            TextButton(onClick = { local = local.copy(faqItems = local.faqItems.filterIndexed { i, _ -> i != index }) }) { Text("حذف السؤال") }
                        }
                        OutlinedButton(onClick = { local = local.copy(faqItems = local.faqItems + SiteFaqEntry()) }, modifier = Modifier.fillMaxWidth()) { Text("إضافة سؤال جديد") }
                    } else if (local.sectionType == "trust") {
                        Text("عناصر الثقة", fontWeight = FontWeight.SemiBold)
                        local.trustItems.forEachIndexed { index, entry ->
                            OutlinedTextField(
                                value = entry.icon,
                                onValueChange = { value -> local = local.copy(trustItems = local.trustItems.mapIndexed { i, old -> if (i == index) old.copy(icon = value) else old }) },
                                label = { Text("الرمز أو الأيقونة") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                value = entry.title,
                                onValueChange = { value -> local = local.copy(trustItems = local.trustItems.mapIndexed { i, old -> if (i == index) old.copy(title = value) else old }) },
                                label = { Text("عنوان عنصر الثقة") },
                                modifier = Modifier.fillMaxWidth()
                            )
                            OutlinedTextField(
                                value = entry.description,
                                onValueChange = { value -> local = local.copy(trustItems = local.trustItems.mapIndexed { i, old -> if (i == index) old.copy(description = value) else old }) },
                                label = { Text("وصف عنصر الثقة") },
                                modifier = Modifier.fillMaxWidth(),
                                minLines = 2
                            )
                            TextButton(onClick = { local = local.copy(trustItems = local.trustItems.filterIndexed { i, _ -> i != index }) }) { Text("حذف العنصر") }
                        }
                        OutlinedButton(onClick = { local = local.copy(trustItems = local.trustItems + SiteTrustEntry()) }, modifier = Modifier.fillMaxWidth()) { Text("إضافة عنصر ثقة") }
                    }'''
    editor_text = once(editor_text, custom_title_field, section_type_controls, "FAQ and trust editor controls")
editor_path.write_text(editor_text, encoding="utf-8")

print("FAQ/trust section models, editors and independent SEO fields applied.")


# Keep both device previews faithful to the FAQ and trust section types.
phone_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/PhoneMockupView.kt"
if phone_path.is_file():
    phone_text = phone_path.read_text(encoding="utf-8")
    phone_text = once(
        phone_text,
        "                        Text(section.text, fontSize = 10.sp)",
        '''                        if (section.sectionType == "faq") {
                            section.faqItems.forEach { item ->
                                Column(Modifier.fillMaxWidth().padding(top = 6.dp)) {
                                    Text(item.question, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                                    Text(item.answer, fontSize = 9.sp, color = Color.DarkGray)
                                }
                            }
                        } else if (section.sectionType == "trust") {
                            section.trustItems.forEach { item ->
                                Row(Modifier.fillMaxWidth().padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Text(item.icon, fontSize = 15.sp, color = iconColor)
                                    Spacer(Modifier.width(7.dp))
                                    Column(Modifier.weight(1f)) {
                                        Text(item.title, fontWeight = FontWeight.Bold, fontSize = 10.sp)
                                        Text(item.description, fontSize = 9.sp, color = Color.DarkGray)
                                    }
                                }
                            }
                        } else Text(section.text, fontSize = 10.sp)''',
        "phone preview FAQ/trust rendering"
    )
    phone_path.write_text(phone_text, encoding="utf-8")

desktop_path = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/DesktopMockupView.kt"
if desktop_path.is_file():
    desktop_text = desktop_path.read_text(encoding="utf-8")
    desktop_text = once(
        desktop_text,
        '                        Text(block.text,fontSize=13.sp)',
        '''                        if (block.sectionType == "faq") {
                            block.faqItems.forEach { item ->
                                Column(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                                    Text(item.question, fontWeight = FontWeight.Bold, fontSize = 14.sp)
                                    Text(item.answer, fontSize = 13.sp, color = Color.DarkGray)
                                }
                            }
                        } else if (block.sectionType == "trust") {
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                block.trustItems.forEach { item ->
                                    Column(Modifier.weight(1f).padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text(item.icon, fontSize = 22.sp, color = Color(0xFFC96F92))
                                        Text(item.title, fontWeight = FontWeight.Bold, fontSize = 13.sp, textAlign = TextAlign.Center)
                                        Text(item.description, fontSize = 12.sp, textAlign = TextAlign.Center)
                                    }
                                }
                            }
                        } else Text(block.text,fontSize=13.sp)''',
        "desktop preview FAQ/trust rendering"
    )
    desktop_path.write_text(desktop_text, encoding="utf-8")

