-- Elory operations hardening: order-linked Prime, manual Prime administration,
-- transactional shipping writes, authenticated staff management and permission checks.
BEGIN;

CREATE OR REPLACE FUNCTION public.activate_prime_from_paid_order()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  v_existing_active boolean := false;
BEGIN
  IF coalesce(NEW.prime_requested, false) IS NOT TRUE THEN
    RETURN NEW;
  END IF;

  IF NEW.user_id IS NULL THEN
    RAISE EXCEPTION 'يجب تسجيل الدخول لشراء Elory Prime';
  END IF;

  IF TG_OP = 'INSERT' THEN
    SELECT EXISTS (
      SELECT 1
      FROM public.prime_subscriptions ps
      WHERE ps.user_id = NEW.user_id
        AND ps.active IS TRUE
        AND ps.status = 'active'
        AND ps.expires_at > now()
    ) INTO v_existing_active;

    IF v_existing_active THEN
      RAISE EXCEPTION 'اشتراك Elory Prime نشط بالفعل لهذا الحساب';
    END IF;

    INSERT INTO public.prime_subscriptions(
      user_id, started_at, expires_at, active, created_at,
      free_shipping_limit, free_shipping_used, discount_percent,
      packaging_enabled, price, payment_reference, status, order_id
    )
    VALUES(
      NEW.user_id, now(), now() + interval '30 days', false, now(),
      6, 0, 10, true, 300, 'ELORY-ORDER-' || NEW.id::text, 'pending', NEW.id
    )
    ON CONFLICT (order_id) WHERE order_id IS NOT NULL DO NOTHING;

    RETURN NEW;
  END IF;

  IF coalesce(NEW.status, '') IN ('فشل الدفع', 'فشل إنشاء الدفع', 'ملغي', 'ملغى') THEN
    UPDATE public.prime_subscriptions
       SET active = false, status = 'failed'
     WHERE order_id = NEW.id
       AND user_id = NEW.user_id
       AND status = 'pending';
    RETURN NEW;
  END IF;

  -- Membership requested with an order is activated only after delivery,
  -- regardless of payment method. Repeated status updates are idempotent.
  IF trim(coalesce(NEW.status, '')) = 'تم التسليم'
     AND trim(coalesce(OLD.status, '')) IS DISTINCT FROM 'تم التسليم' THEN
    UPDATE public.prime_subscriptions
       SET active = true,
           status = 'active',
           started_at = now(),
           expires_at = now() + interval '30 days',
           free_shipping_limit = 6,
           free_shipping_used = 0,
           discount_percent = 10,
           packaging_enabled = true,
           price = 300
     WHERE order_id = NEW.id
       AND user_id = NEW.user_id
       AND status = 'pending';
  END IF;

  RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_apply_shipping_governorate_price(p_governorate text, p_price numeric)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
declare
  v_count integer;
  g public.shipping_governorates%rowtype;
begin

  if not public.has_staff_permission('shipping.manage') then
    raise exception 'ليس لديك صلاحية إدارة الشحن';
  end if;

  if nullif(trim(p_governorate),'') is null
     or p_price is null
     or p_price < 0 then
    raise exception 'بيانات سعر الشحن غير صحيحة';
  end if;

  insert into public.shipping_governorates(
    governorate,
    price,
    active,
    centers_enabled,
    updated_at
  )
  values(
    trim(p_governorate),
    p_price,
    true,
    true,
    now()
  )
  on conflict(governorate)
  do update set
    price=excluded.price,
    updated_at=now()
  returning *
  into g;

  update public.shipping_centers
  set price=p_price
  where governorate=trim(p_governorate);

  get diagnostics v_count=row_count;

  return jsonb_build_object(
    'governorate',g.governorate,
    'price',g.price,
    'updated_centers',v_count,
    'active',g.active,
    'centers_enabled',g.centers_enabled
  );

end;
$function$;

CREATE OR REPLACE FUNCTION public.admin_grant_prime_by_email(p_email text, p_days integer DEFAULT 30)
 RETURNS TABLE(success boolean, user_id uuid, expires_at timestamp with time zone, message text)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  target_id uuid;
  current_expiry timestamptz;
  new_expiry timestamptz;
BEGIN
  IF NOT public.has_staff_permission('prime.manage') THEN
    RETURN QUERY SELECT false, null::uuid, null::timestamptz, 'ليس لديك صلاحية تفعيل Prime يدويًا'::text;
    RETURN;
  END IF;
  IF nullif(trim(p_email), '') IS NULL OR coalesce(p_days, 0) < 1 OR p_days > 365 THEN
    RETURN QUERY SELECT false, null::uuid, null::timestamptz, 'البريد أو عدد الأيام غير صحيح (1 إلى 365)'::text;
    RETURN;
  END IF;

  SELECT u.id INTO target_id
    FROM auth.users u
   WHERE lower(u.email) = lower(trim(p_email))
   LIMIT 1;
  IF target_id IS NULL THEN
    RETURN QUERY SELECT false, null::uuid, null::timestamptz, 'البريد غير مسجل في حسابات Elory'::text;
    RETURN;
  END IF;

  SELECT max(ps.expires_at) INTO current_expiry
    FROM public.prime_subscriptions ps
   WHERE ps.user_id = target_id
     AND ps.active IS TRUE
     AND ps.status = 'active'
     AND ps.expires_at > now();

  new_expiry := greatest(coalesce(current_expiry, now()), now()) + make_interval(days => p_days);

  UPDATE public.prime_subscriptions AS ps
     SET active = false,
         status = CASE WHEN ps.expires_at <= now() THEN 'expired' ELSE 'superseded' END
   WHERE ps.user_id = target_id
     AND ps.active IS TRUE;

  INSERT INTO public.prime_subscriptions(
    user_id, started_at, expires_at, active, created_at,
    free_shipping_limit, free_shipping_used, discount_percent,
    packaging_enabled, price, status, order_id
  )
  VALUES(
    target_id, now(), new_expiry, true, now(),
    6, 0, 10, true, 300, 'active', null
  );

  RETURN QUERY SELECT true, target_id, new_expiry, 'تم تفعيل Elory Prime بنجاح'::text;
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_list_prime_subscriptions()
 RETURNS SETOF jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
  IF NOT public.has_staff_permission('prime.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية مشاهدة اشتراكات Prime';
  END IF;

  RETURN QUERY
  SELECT
    to_jsonb(ps) ||
    jsonb_build_object(
      'customer_name', coalesce(
        nullif(latest_order.customer_name, ''),
        nullif(u.raw_user_meta_data ->> 'full_name', ''),
        nullif(u.raw_user_meta_data ->> 'name', ''),
        u.email,
        'عميل Elory'
      ),
      'phone', coalesce(nullif(latest_order.phone, ''), nullif(u.raw_user_meta_data ->> 'phone', ''), ''),
      'email', coalesce(u.email, ''),
      'total_orders', coalesce(order_stats.total_orders, 0),
      'total_saved', coalesce(order_stats.total_saved, 0)
    )
  FROM public.prime_subscriptions ps
  LEFT JOIN auth.users u ON u.id = ps.user_id
  LEFT JOIN LATERAL (
    SELECT o.customer_name, o.phone
      FROM public.orders o
     WHERE o.user_id = ps.user_id
     ORDER BY o.created_at DESC
     LIMIT 1
  ) latest_order ON true
  LEFT JOIN LATERAL (
    SELECT
      count(*) FILTER (WHERE coalesce(o.prime, false))::integer AS total_orders,
      coalesce(sum(
        coalesce(o.prime_discount, 0) +
        CASE WHEN coalesce(o.prime_free_shipping, false)
             THEN coalesce(o.shipping_cost, 0) ELSE 0 END
      ), 0)::numeric AS total_saved
    FROM public.orders o
    WHERE o.user_id = ps.user_id
  ) order_stats ON true
  ORDER BY ps.created_at DESC NULLS LAST, ps.started_at DESC NULLS LAST;
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_save_shipping_center(p_id text DEFAULT ''::text, p_governorate text DEFAULT ''::text, p_center text DEFAULT ''::text, p_price numeric DEFAULT 0, p_active boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  v_result jsonb;
  v_updated boolean := false;
BEGIN
  IF NOT public.has_staff_permission('shipping.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية إدارة الشحن';
  END IF;
  IF nullif(trim(p_governorate), '') IS NULL THEN
    RAISE EXCEPTION 'المحافظة مطلوبة';
  END IF;
  IF nullif(trim(p_center), '') IS NULL THEN
    RAISE EXCEPTION 'المركز مطلوب';
  END IF;
  IF p_price IS NULL OR p_price < 0 THEN
    RAISE EXCEPTION 'سعر الشحن غير صحيح';
  END IF;

  IF nullif(trim(coalesce(p_id, '')), '') IS NOT NULL THEN
    UPDATE public.shipping_centers
       SET governorate = trim(p_governorate),
           center = trim(p_center),
           price = p_price,
           active = coalesce(p_active, true)
     WHERE id::text = trim(p_id);
    v_updated := FOUND;
  END IF;

  IF NOT v_updated THEN
    INSERT INTO public.shipping_centers(governorate, center, price, active)
    VALUES(trim(p_governorate), trim(p_center), p_price, coalesce(p_active, true))
    ON CONFLICT(governorate, center)
    DO UPDATE SET price = excluded.price, active = excluded.active;
  END IF;

  SELECT to_jsonb(c)
    INTO v_result
    FROM public.shipping_centers c
   WHERE lower(c.governorate) = lower(trim(p_governorate))
     AND lower(c.center) = lower(trim(p_center))
   ORDER BY c.created_at DESC NULLS LAST
   LIMIT 1;

  RETURN v_result;
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_save_shipping_governorate(p_governorate text, p_price numeric, p_active boolean DEFAULT true, p_centers_enabled boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  r public.shipping_governorates%rowtype;
BEGIN
  IF NOT public.has_staff_permission('shipping.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية إدارة الشحن';
  END IF;

  IF nullif(trim(p_governorate), '') IS NULL
     OR p_price IS NULL
     OR p_price < 0 THEN
    RAISE EXCEPTION 'بيانات سعر الشحن غير صحيحة';
  END IF;

  INSERT INTO public.shipping_governorates(
    governorate, price, active, centers_enabled, updated_at
  )
  VALUES(
    trim(p_governorate), p_price,
    coalesce(p_active, true),
    coalesce(p_centers_enabled, true),
    now()
  )
  ON CONFLICT(governorate)
  DO UPDATE SET
    price = excluded.price,
    active = excluded.active,
    centers_enabled = excluded.centers_enabled,
    updated_at = now()
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'governorate', r.governorate,
    'price', r.price,
    'active', r.active,
    'centers_enabled', r.centers_enabled
  );
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_set_prime_subscription_active(p_subscription_id uuid, p_active boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  r public.prime_subscriptions%rowtype;
  v_user_id uuid;
BEGIN
  IF NOT public.has_staff_permission('prime.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية إدارة اشتراكات Prime';
  END IF;
  IF p_subscription_id IS NULL THEN
    RAISE EXCEPTION 'معرّف الاشتراك غير صحيح';
  END IF;

  SELECT user_id INTO v_user_id
    FROM public.prime_subscriptions
   WHERE id = p_subscription_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'اشتراك Prime غير موجود';
  END IF;

  IF coalesce(p_active,false) THEN
    UPDATE public.prime_subscriptions
       SET active = false,
           status = 'superseded'
     WHERE user_id = v_user_id
       AND id <> p_subscription_id
       AND active IS TRUE;
  END IF;

  UPDATE public.prime_subscriptions
     SET active = coalesce(p_active,false),
         status = CASE WHEN coalesce(p_active,false) THEN 'active' ELSE 'expired' END,
         started_at = CASE WHEN coalesce(p_active,false) THEN now() ELSE started_at END,
         expires_at = CASE WHEN coalesce(p_active,false) THEN now() + interval '30 days' ELSE expires_at END,
         free_shipping_limit = CASE WHEN coalesce(p_active,false) THEN 6 ELSE free_shipping_limit END,
         free_shipping_used = CASE WHEN coalesce(p_active,false) THEN 0 ELSE free_shipping_used END,
         discount_percent = CASE WHEN coalesce(p_active,false) THEN 10 ELSE discount_percent END,
         packaging_enabled = CASE WHEN coalesce(p_active,false) THEN true ELSE packaging_enabled END,
         price = CASE WHEN coalesce(p_active,false) THEN 300 ELSE price END
   WHERE id = p_subscription_id
   RETURNING * INTO r;

  RETURN to_jsonb(r);
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_set_staff_active(p_staff_id uuid, p_active boolean)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  r public.staff_profiles%rowtype;
  v_actor_email text;
BEGIN
  IF NOT public.has_staff_permission('staff.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية إدارة الموظفين';
  END IF;

  SELECT lower(coalesce(u.email, '')) INTO v_actor_email
    FROM auth.users u WHERE u.id = auth.uid();

  IF p_staff_id = auth.uid() AND coalesce(p_active,false) IS NOT TRUE THEN
    RAISE EXCEPTION 'لا يمكن إيقاف حسابك الحالي من داخل الداشبورد';
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.staff_profiles sp
    WHERE sp.id = p_staff_id AND lower(coalesce(sp.role,'')) = 'owner'
  ) AND v_actor_email <> 'ilnemrawi@gmail.com' THEN
    RAISE EXCEPTION 'إيقاف حساب المالك متاح لحساب المالك فقط';
  END IF;

  UPDATE public.staff_profiles
     SET active = coalesce(p_active,false), updated_at = now()
   WHERE id = p_staff_id
   RETURNING * INTO r;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'الموظف غير موجود';
  END IF;

  RETURN jsonb_build_object(
    'id',r.id,'email',r.email,'name',r.name,'role',r.role,
    'permissions',coalesce(r.permissions,'{}'::jsonb),
    'active',r.active,'updated_at',r.updated_at,'created_at',r.created_at
  );
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_update_order_status(p_order_id uuid, p_status text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  r public.orders%rowtype;
BEGIN
  IF NOT public.has_staff_permission('orders.edit') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية تعديل الطلبات';
  END IF;

  IF trim(coalesce(p_status,'')) NOT IN (
    'جديد',
    'جاري التأكيد',
    'جاري التجهيز',
    'تم الشحن',
    'تم التسليم',
    'ملغي'
  ) THEN
    RAISE EXCEPTION 'حالة الطلب غير صحيحة';
  END IF;

  UPDATE public.orders
     SET status = trim(p_status)
   WHERE id = p_order_id
   RETURNING * INTO r;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'الطلب غير موجود';
  END IF;

  RETURN to_jsonb(r);
END;
$function$;

CREATE OR REPLACE FUNCTION public.admin_upsert_staff_by_email(p_email text, p_name text DEFAULT NULL::text, p_role text DEFAULT 'staff'::text, p_permissions jsonb DEFAULT '{}'::jsonb, p_active boolean DEFAULT true)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  v_uid uuid;
  v_email text := lower(trim(coalesce(p_email,'')));
  v_role text := lower(trim(coalesce(p_role,'staff')));
  v_actor_email text;
  r public.staff_profiles%rowtype;
BEGIN
  IF NOT public.has_staff_permission('staff.manage') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية إدارة الموظفين';
  END IF;

  SELECT lower(coalesce(u.email, '')) INTO v_actor_email
    FROM auth.users u WHERE u.id = auth.uid();

  IF v_email = '' THEN
    RAISE EXCEPTION 'البريد الإلكتروني مطلوب';
  END IF;
  IF v_role NOT IN ('staff','admin','manager','owner') THEN
    RAISE EXCEPTION 'الدور الوظيفي غير صحيح';
  END IF;

  IF v_role IN ('admin','manager','owner') AND v_actor_email <> 'ilnemrawi@gmail.com' THEN
    RAISE EXCEPTION 'إنشاء أو تعديل مدير نظام أو مالك متاح لحساب المالك فقط';
  END IF;

  SELECT id INTO v_uid
    FROM auth.users
   WHERE lower(email) = v_email
   LIMIT 1;

  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'لا يوجد حساب مستخدم بهذا البريد. استخدم إنشاء حساب الموظف من الداشبورد أولاً.';
  END IF;

  IF v_uid = auth.uid() AND v_role <> 'owner' THEN
    RAISE EXCEPTION 'لا يمكن تغيير دور حساب المالك الحالي';
  END IF;

  INSERT INTO public.staff_profiles(
    id, email, name, role, permissions, active, updated_at
  )
  VALUES(
    v_uid, v_email, p_name, v_role,
    coalesce(p_permissions,'{}'::jsonb),
    coalesce(p_active,true), now()
  )
  ON CONFLICT(id)
  DO UPDATE SET
    email=excluded.email,
    name=excluded.name,
    role=excluded.role,
    permissions=excluded.permissions,
    active=excluded.active,
    updated_at=now()
  RETURNING * INTO r;

  RETURN jsonb_build_object(
    'id',r.id,'email',r.email,'name',r.name,'role',r.role,
    'permissions',coalesce(r.permissions,'{}'::jsonb),
    'active',r.active,'updated_at',r.updated_at,'created_at',r.created_at
  );
END;
$function$;

CREATE OR REPLACE FUNCTION public.has_staff_permission(p_permission text)
 RETURNS boolean
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  v_uid uuid := auth.uid();
  v_email text;
  v_role text;
  v_permissions jsonb;
  v_active boolean;
  v_storage_key text;
  v_alias_key text;
BEGIN
  IF v_uid IS NULL THEN
    RETURN false;
  END IF;

  SELECT lower(coalesce(u.email, ''))
    INTO v_email
    FROM auth.users u
   WHERE u.id = v_uid;

  SELECT sp.role, sp.permissions, sp.active
    INTO v_role, v_permissions, v_active
    FROM public.staff_profiles sp
   WHERE sp.id = v_uid
   LIMIT 1;

  -- The designated owner account is the only unconditional administrator.
  IF v_email = 'ilnemrawi@gmail.com' THEN
    RETURN coalesce(v_active, false);
  END IF;

  IF coalesce(v_active, false) IS NOT TRUE THEN
    RETURN false;
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

DROP TRIGGER IF EXISTS elory_prime_order_lifecycle ON public.orders;
CREATE TRIGGER elory_prime_order_lifecycle
AFTER INSERT OR UPDATE OF status, prime_requested, user_id
ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.activate_prime_from_paid_order();


REVOKE ALL ON FUNCTION public.admin_list_prime_subscriptions() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_list_prime_subscriptions() TO authenticated;
REVOKE ALL ON FUNCTION public.admin_set_prime_subscription_active(uuid, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_set_prime_subscription_active(uuid, boolean) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_grant_prime_by_email(text, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_grant_prime_by_email(text, integer) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_save_shipping_governorate(text, numeric, boolean, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_save_shipping_governorate(text, numeric, boolean, boolean) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_apply_shipping_governorate_price(text, numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_apply_shipping_governorate_price(text, numeric) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_save_shipping_center(text, text, text, numeric, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_save_shipping_center(text, text, text, numeric, boolean) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_upsert_staff_by_email(text, text, text, jsonb, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_upsert_staff_by_email(text, text, text, jsonb, boolean) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_set_staff_active(uuid, boolean) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_set_staff_active(uuid, boolean) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_update_order_status(uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_update_order_status(uuid, text) TO authenticated;

COMMIT;
