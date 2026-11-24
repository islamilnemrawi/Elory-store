from pathlib import Path
import os

ROOT = Path(os.environ["PROJECT_DIR"]).resolve()
def patch_file(rel, transform):
    path = ROOT / rel
    source = path.read_text(encoding="utf-8")
    updated = transform(source)
    if updated == source:
        raise SystemExit(f"No offer UUID repair applied to {rel}; expected source anchor was not found")
    path.write_text(updated, encoding="utf-8")

REMOTE = "app/src/main/java/com/pinky/dashboard/data/remote/SupabaseClient.kt"
REPO = "app/src/main/java/com/pinky/dashboard/data/repository/RepositoriesImpl.kt"
VM = "app/src/main/java/com/pinky/dashboard/ui/PinkyViewModel.kt"

def patch_remote(source):
    def clone_write_dto(current, read_name, write_name):
        if f"data class {write_name}(" in current: return current
        start = current.find(f"data class {read_name}(")
        if start < 0: raise SystemExit(f"{read_name} declaration not found")
        end = current.find("\n)", start)
        if end < 0: raise SystemExit(f"{read_name} closing delimiter not found")
        block = current[start:end + 2]
        write_block = block.replace(f"data class {read_name}(", f"data class {write_name}(", 1)
        old_id = '@Json(name = "id") val id: String,'
        if write_block.count(old_id) != 1: raise SystemExit(f"{read_name} ID field missing or duplicated")
        write_block = write_block.replace(old_id, '@Json(name = "id") val id: String? = null,', 1)
        return current[:end + 2] + "\n\n@JsonClass(generateAdapter = true)\n" + write_block + current[end + 2:]

    source = clone_write_dto(source, "SupabaseOfferDto", "SupabaseOfferUpsertDto")
    source = clone_write_dto(source, "SupabaseBannerDto", "SupabaseBannerUpsertDto")
    pairs = [
        ("""    @POST("rest/v1/offers")
    suspend fun upsertOffer(
        @Body offer: SupabaseOfferDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates"
    ): Response<Unit>""",
         """    @POST("rest/v1/offers")
    suspend fun upsertOffer(
        @Body offer: SupabaseOfferUpsertDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates,return=representation"
    ): Response<List<SupabaseOfferDto>>"""),
        ("""    @POST("rest/v1/banners")
    suspend fun upsertBanner(
        @Body banner: SupabaseBannerDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates"
    ): Response<Unit>""",
         """    @POST("rest/v1/banners")
    suspend fun upsertBanner(
        @Body banner: SupabaseBannerUpsertDto,
        @Header("Prefer") prefer: String = "resolution=merge-duplicates,return=representation"
    ): Response<List<SupabaseBannerDto>>""")
    ]
    for old, new in pairs:
        if new in source: continue
        if source.count(old) != 1: raise SystemExit("Offer/banner upsert API declaration missing or duplicated")
        source = source.replace(old, new, 1)
    return source

patch_file(REMOTE, patch_remote)

def patch_repository(source):
    save_start = source.find("    override suspend fun saveOffer(offer: Offer)")
    save_end = source.find("    override suspend fun deleteOffer(", save_start)
    if save_start < 0 or save_end < 0: raise SystemExit("OfferRepository save/delete method boundaries not found")
    block = source[save_start:save_end]
    if "val remoteOfferId =" not in block:
        old = """            val isBanner = offer.isBanner || offer.id.startsWith("ban_")
            val response = if (isBanner) {"""
        new = """            val isBanner = offer.isBanner || offer.id.startsWith("ban_")
            // Local UI IDs (off_*/ban_*) are not PostgreSQL UUIDs. Existing banner
            // cache IDs carry a ban_ prefix; strip it only when it wraps a real UUID.
            val remoteOfferId = (if (isBanner) offer.id.removePrefix("ban_") else offer.id)
                .takeIf(::isCanonicalProductUuid)
            val response = if (isBanner) {"""
        if block.count(old) != 1: raise SystemExit("Offer save ID preparation anchor missing or duplicated")
        block = block.replace(old, new, 1)
        if block.count("id = offer.id,") != 3: raise SystemExit("Offer DTO/cache ID anchors missing or duplicated")
        block = block.replace("id = offer.id,", "id = remoteOfferId,", 2)

        upsert_start = block.find("            val response = if (isBanner) {")
        entity_start = block.find("            val entity = OfferEntity(", upsert_start)
        if upsert_start < 0 or entity_start < 0:
            raise SystemExit("Offer upsert/cache block boundaries not found")
        new_upsert = """            val persistedRemoteId: String? = if (isBanner) {
                val bannerResponse = SupabaseClient.service.upsertBanner(
                    SupabaseBannerUpsertDto(
                        id = remoteOfferId,
                        title = offer.title,
                        subtitle = offer.description,
                        image = offer.imageUrl,
                        buttonText = offer.buttonText,
                        buttonAction = offer.targetCategoryId ?: offer.targetCategoryName,
                        sortOrder = offer.sortOrder,
                        active = offer.isActive
                    )
                )
                if (!bannerResponse.isSuccessful) {
                    return@withContext Result.failure(Exception("فشل حفظ البانر على Supabase (HTTP ${bannerResponse.code()})."))
                }
                bannerResponse.body()?.firstOrNull()?.id
            } else {
                val offerResponse = SupabaseClient.service.upsertOffer(
                    SupabaseOfferUpsertDto(
                        id = remoteOfferId,
                        title = offer.title,
                        description = offer.description,
                        discount = offer.discountText.filter { it.isDigit() || it == '.' }.toDoubleOrNull(),
                        image = offer.imageUrl,
                        active = offer.isActive,
                        startsAt = offer.startDate.toSupabaseIsoTimestamp(),
                        endsAt = offer.endDate.toSupabaseIsoTimestamp(),
                        buttonText = offer.buttonText,
                        targetCategory = offer.targetCategoryId ?: offer.targetCategoryName,
                        sortOrder = offer.sortOrder,
                        isActive = offer.isActive
                    )
                )
                if (!offerResponse.isSuccessful) {
                    return@withContext Result.failure(Exception("فشل حفظ العرض على Supabase (HTTP ${offerResponse.code()})."))
                }
                offerResponse.body()?.firstOrNull()?.id
            }

            val persistedId = persistedRemoteId?.takeIf(::isCanonicalProductUuid)
                ?: remoteOfferId
                ?: throw IllegalStateException("Supabase saved the offer but did not return its generated UUID.")
            val savedId = if (isBanner) "ban_$persistedId" else persistedId
            val savedOffer = offer.copy(id = savedId)

"""
        block = block[:upsert_start] + new_upsert + block[entity_start:]
        old_entity = """            val entity = OfferEntity(
                id = offer.id,"""
        new_entity = """            val entity = OfferEntity(
                id = savedId,"""
        if block.count(old_entity) != 1:
            raise SystemExit("Offer cache entity ID anchor missing or duplicated")
        block = block.replace(old_entity, new_entity, 1)
        if block.count("Result.success(offer)") != 1: raise SystemExit("Offer save result anchor missing or duplicated")
        block = block.replace("Result.success(offer)", "Result.success(savedOffer)", 1)
    source = source[:save_start] + block + source[save_end:]

    delete_start = source.find("    override suspend fun deleteOffer(offerId: String)")
    delete_end = source.find("    override suspend fun syncOffers()", delete_start)
    if delete_start < 0 or delete_end < 0: raise SystemExit("Offer delete/sync method boundaries not found")
    delete_block = source[delete_start:delete_end]
    if "val remoteId = if (isBanner)" not in delete_block:
        old_delete = """            val isBanner = offerId.startsWith("ban_")
            val response = if (isBanner) {
                SupabaseClient.service.deleteBanner("eq.$offerId")
            } else {
                SupabaseClient.service.deleteOffer("eq.$offerId")
            }"""
        new_delete = """            val isBanner = offerId.startsWith("ban_")
            val remoteId = if (isBanner) offerId.removePrefix("ban_") else offerId
            if (!isCanonicalProductUuid(remoteId)) {
                return@withContext Result.failure(IllegalArgumentException("معرّف العرض غير صالح للحذف من Supabase."))
            }
            val response = if (isBanner) {
                SupabaseClient.service.deleteBanner("eq.$remoteId")
            } else {
                SupabaseClient.service.deleteOffer("eq.$remoteId")
            }"""
        if delete_block.count(old_delete) != 1: raise SystemExit("Offer delete UUID normalization anchor missing or duplicated")
        delete_block = delete_block.replace(old_delete, new_delete, 1)
    return source[:delete_start] + delete_block + source[delete_end:]

patch_file(REPO, patch_repository)

def patch_view_model(source):
    old_save = """    fun saveOffer(offer: Offer) {
        viewModelScope.launch {
            offerRepository.saveOffer(offer)
        }
    }"""
    new_save = """    fun saveOffer(offer: Offer) {
        viewModelScope.launch {
            val result = offerRepository.saveOffer(offer)
            if (result.isSuccess) {
                val syncResult = offerRepository.syncOffers()
                _syncError.value = syncResult.exceptionOrNull()?.let {
                    "تم حفظ العرض، لكن تعذرت مزامنة القائمة: ${it.localizedMessage ?: "خطأ غير معروف"}"
                }
            } else {
                val error = result.exceptionOrNull()
                _syncError.value = "تعذر حفظ العرض: ${error?.localizedMessage ?: "خطأ غير معروف"}"
                android.util.Log.e("EloryOffers", "Offer save failed.", error)
            }
        }
    }"""
    if new_save not in source:
        if source.count(old_save) != 1: raise SystemExit("PinkyViewModel.saveOffer anchor missing or duplicated")
        source = source.replace(old_save, new_save, 1)

    old_delete = """    fun deleteOffer(offerId: String) {
        viewModelScope.launch {
            offerRepository.deleteOffer(offerId)
        }
    }"""
    new_delete = """    fun deleteOffer(offerId: String) {
        viewModelScope.launch {
            val result = offerRepository.deleteOffer(offerId)
            if (result.isSuccess) {
                val syncResult = offerRepository.syncOffers()
                _syncError.value = syncResult.exceptionOrNull()?.let {
                    "تم حذف العرض، لكن تعذرت مزامنة القائمة: ${it.localizedMessage ?: "خطأ غير معروف"}"
                }
            } else {
                val error = result.exceptionOrNull()
                _syncError.value = "تعذر حذف العرض: ${error?.localizedMessage ?: "خطأ غير معروف"}"
                android.util.Log.e("EloryOffers", "Offer delete failed.", error)
            }
        }
    }"""
    if new_delete not in source:
        if source.count(old_delete) != 1: raise SystemExit("PinkyViewModel.deleteOffer anchor missing or duplicated")
        source = source.replace(old_delete, new_delete, 1)
    return source

patch_file(VM, patch_view_model)
print("PASS: Offer/banner UUID create-update-delete and read-after-write repair.")
