-- Make website version restore and draft cleanup atomic.
-- A stale editor draft must never survive a successful published restore.
CREATE OR REPLACE FUNCTION public.admin_restore_site_customization_version(p_version_id bigint)
RETURNS boolean
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $function$
DECLARE
    v_saved_config jsonb;
    v_saved_settings jsonb;
    v_live_config jsonb;
    v_current_store_open jsonb;
    v_updated_rows integer;
BEGIN
    IF auth.uid() IS NULL OR NOT public.elory_can_edit_site() THEN
        RAISE EXCEPTION 'Not authorized to restore website versions' USING ERRCODE = '42501';
    END IF;

    SELECT versions.config, versions.store_settings
      INTO v_saved_config, v_saved_settings
      FROM elory_cms_private.site_customization_versions AS versions
     WHERE versions.id = p_version_id;

    IF v_saved_config IS NULL OR v_saved_settings IS NULL THEN
        RAISE EXCEPTION 'Website version was not found' USING ERRCODE = 'P0002';
    END IF;

    SELECT sc.config
      INTO v_live_config
      FROM public.site_customizations AS sc
     WHERE sc.id = 1
     FOR UPDATE;

    IF v_live_config IS NULL THEN
        RAISE EXCEPTION 'Current website configuration was not found' USING ERRCODE = 'P0002';
    END IF;

    -- Save the current state before restoring, so the operation itself is reversible.
    PERFORM public.admin_create_site_customization_snapshot('نسخة تلقائية قبل الاستعادة');

    -- Preserve the live switch exactly as it is now; never restore its older snapshot value.
    v_current_store_open := v_live_config #> '{global,isStoreOpen}';
    IF pg_catalog.jsonb_typeof(v_saved_config->'global') IS DISTINCT FROM 'object' THEN
        v_saved_config := pg_catalog.jsonb_set(
            COALESCE(v_saved_config, '{}'::jsonb),
            '{global}',
            '{}'::jsonb,
            true
        );
    END IF;

    IF v_current_store_open IS NULL THEN
        v_saved_config := v_saved_config #- '{global,isStoreOpen}';
    ELSE
        v_saved_config := pg_catalog.jsonb_set(
            v_saved_config,
            '{global,isStoreOpen}',
            v_current_store_open,
            true
        );
    END IF;

    UPDATE public.site_customizations
       SET config = v_saved_config,
           updated_at = pg_catalog.now()
     WHERE id = 1;

    GET DIAGNOSTICS v_updated_rows = ROW_COUNT;
    IF v_updated_rows <> 1 THEN
        RAISE EXCEPTION 'Could not restore website customization row' USING ERRCODE = 'P0002';
    END IF;

    UPDATE public.store_settings
       SET store_name = CASE WHEN v_saved_settings ? 'store_name' THEN v_saved_settings->>'store_name' ELSE store_name END,
           whatsapp = CASE WHEN v_saved_settings ? 'whatsapp' THEN v_saved_settings->>'whatsapp' ELSE whatsapp END,
           instagram = CASE WHEN v_saved_settings ? 'instagram' THEN v_saved_settings->>'instagram' ELSE instagram END,
           facebook = CASE WHEN v_saved_settings ? 'facebook' THEN v_saved_settings->>'facebook' ELSE facebook END,
           logo = CASE WHEN v_saved_settings ? 'logo' THEN v_saved_settings->>'logo' ELSE logo END,
           updated_at = pg_catalog.now()
     WHERE id = 1;

    GET DIAGNOSTICS v_updated_rows = ROW_COUNT;
    IF v_updated_rows <> 1 THEN
        RAISE EXCEPTION 'Could not restore store settings row' USING ERRCODE = 'P0002';
    END IF;

    -- Clear the editor draft in the same transaction as restoring published settings.
    -- If draft cleanup fails, PostgreSQL rolls back the restore as well.
    PERFORM public.admin_clear_site_customization_draft();

    RETURN true;
END;
$function$;


REVOKE ALL ON FUNCTION public.admin_restore_site_customization_version(bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_restore_site_customization_version(bigint) TO authenticated;
