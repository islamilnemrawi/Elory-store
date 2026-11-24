-- Elory: align active owner role authorization with dashboard role mapping.
-- Applied to the active Elory Supabase project on 2026-11-17.
-- No table data or RLS policies are changed by this migration.
CREATE OR REPLACE FUNCTION public.has_staff_permission(p_permission text)
RETURNS boolean
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_uid uuid := auth.uid();
  v_role text;
  v_permissions jsonb;
  v_active boolean;
  v_storage_key text;
  v_alias_key text;
BEGIN
  IF v_uid IS NULL THEN
    RETURN false;
  END IF;

  SELECT sp.role, sp.permissions, sp.active
    INTO v_role, v_permissions, v_active
    FROM public.staff_profiles sp
   WHERE sp.id = v_uid
   LIMIT 1;

  IF coalesce(v_active, false) IS NOT TRUE THEN
    RETURN false;
  END IF;

  IF lower(trim(coalesce(v_role, ''))) = 'owner' THEN
    RETURN true;
  END IF;

  v_alias_key := lower(trim(coalesce(p_permission, '')));
  v_storage_key := CASE v_alias_key
    WHEN 'orders.view' THEN 'MANAGE_ORDERS'
    WHEN 'orders.edit' THEN 'UPDATE_ORDER_STATUS'
    WHEN 'orders.delete' THEN 'MANAGE_ORDERS'
    WHEN 'products.view' THEN 'MANAGE_PRODUCTS'
    WHEN 'products.add' THEN 'MANAGE_PRODUCTS'
    WHEN 'products.edit' THEN 'MANAGE_PRODUCTS'
    WHEN 'products.delete' THEN 'MANAGE_PRODUCTS'
    WHEN 'products.manage' THEN 'MANAGE_PRODUCTS'
    WHEN 'products.wholesale_prices' THEN 'VIEW_WHOLESALE_PRICES'
    WHEN 'products.internal_codes' THEN 'VIEW_INTERNAL_CODES'
    WHEN 'categories.manage' THEN 'MANAGE_CATEGORIES'
    WHEN 'offers.manage' THEN 'MANAGE_OFFERS'
    WHEN 'coupons.manage' THEN 'MANAGE_COUPONS'
    WHEN 'customers.manage' THEN 'MANAGE_CUSTOMERS'
    WHEN 'prime.manage' THEN 'MANAGE_PRIME'
    WHEN 'shipping.manage' THEN 'MANAGE_SHIPPING'
    WHEN 'payments.manage' THEN 'MANAGE_PAYMENT_METHODS'
    WHEN 'staff.manage' THEN 'MANAGE_STAFF'
    WHEN 'website.manage' THEN 'MANAGE_WEBSITE_EDITOR'
    WHEN 'site.edit' THEN 'MANAGE_WEBSITE_EDITOR'
    WHEN 'analytics.view' THEN 'VIEW_ANALYTICS'
    WHEN 'analytics.profit' THEN 'VIEW_PROFIT'
    WHEN 'notifications.view' THEN 'VIEW_NOTIFICATIONS'
    WHEN 'settings.manage' THEN 'MANAGE_SETTINGS'
    WHEN 'store.manage' THEN 'MANAGE_SETTINGS'
    WHEN 'dashboard.view' THEN 'VIEW_DASHBOARD'
    ELSE upper(replace(v_alias_key, '.', '_'))
  END;

  IF coalesce((v_permissions ->> p_permission)::boolean, false)
     OR coalesce((v_permissions ->> v_storage_key)::boolean, false) THEN
    RETURN true;
  END IF;

  IF v_alias_key = 'orders.edit'
     AND coalesce((v_permissions ->> 'MANAGE_ORDERS')::boolean, false) THEN
    RETURN true;
  END IF;

  RETURN false;
EXCEPTION
  WHEN invalid_text_representation THEN
    RETURN false;
END;
$function$;
