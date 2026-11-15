-- Harden Elory coupon ownership, per-customer limits, and transactional order redemption.
-- The AFTER INSERT trigger reserves a coupon in the same transaction as the order,
-- so an invalid or concurrently exhausted coupon cannot leave a discounted order behind.

ALTER TABLE public.coupons
  ADD COLUMN IF NOT EXISTS first_order_only boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS per_customer_limit integer DEFAULT 1,
  ADD COLUMN IF NOT EXISTS audience_mode text NOT NULL DEFAULT 'all_customers';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.coupons'::regclass
      AND conname = 'coupons_per_customer_limit_check'
  ) THEN
    ALTER TABLE public.coupons
      ADD CONSTRAINT coupons_per_customer_limit_check
      CHECK (per_customer_limit IS NULL OR per_customer_limit >= 1);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.coupons'::regclass
      AND conname = 'coupons_audience_mode_check'
  ) THEN
    ALTER TABLE public.coupons
      ADD CONSTRAINT coupons_audience_mode_check
      CHECK (audience_mode IN ('all_customers', 'single_customer'));
  END IF;
END;
$$;

-- Codes are checked case-insensitively by the storefront, so uniqueness must be too.
CREATE UNIQUE INDEX IF NOT EXISTS coupons_code_upper_trim_uidx
  ON public.coupons (upper(trim(code)));

CREATE TABLE IF NOT EXISTS public.coupon_redemptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  coupon_id uuid NOT NULL REFERENCES public.coupons(id) ON DELETE RESTRICT,
  order_id uuid NOT NULL UNIQUE REFERENCES public.orders(id) ON DELETE CASCADE,
  phone_normalized text,
  customer_user_id uuid,
  redeemed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS coupon_redemptions_coupon_phone_idx
  ON public.coupon_redemptions (coupon_id, phone_normalized)
  WHERE phone_normalized IS NOT NULL;

CREATE INDEX IF NOT EXISTS coupon_redemptions_coupon_user_idx
  ON public.coupon_redemptions (coupon_id, customer_user_id)
  WHERE customer_user_id IS NOT NULL;

ALTER TABLE public.coupon_redemptions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.coupon_redemptions FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.normalize_egypt_phone(p_phone text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
SET search_path = ''
AS $function$
DECLARE
  v_digits text := pg_catalog.regexp_replace(coalesce(p_phone, ''), '[^0-9]', '', 'g');
BEGIN
  IF v_digits = '' THEN
    RETURN NULL;
  END IF;

  IF left(v_digits, 4) = '0020' THEN
    v_digits := substring(v_digits FROM 3);
  ELSIF length(v_digits) = 11 AND left(v_digits, 1) = '0' THEN
    v_digits := '20' || substring(v_digits FROM 2);
  ELSIF length(v_digits) = 10 AND left(v_digits, 1) = '1' THEN
    v_digits := '20' || v_digits;
  END IF;

  RETURN NULLIF(v_digits, '');
END;
$function$;

REVOKE ALL ON FUNCTION private.normalize_egypt_phone(text) FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.coupon_customer_validation_message(
  p_coupon_id uuid,
  p_subtotal numeric,
  p_phone text,
  p_customer_user_id uuid,
  p_exclude_order_id uuid DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_coupon public.coupons%ROWTYPE;
  v_phone text := private.normalize_egypt_phone(p_phone);
  v_customer_uses integer := 0;
BEGIN
  SELECT * INTO v_coupon
  FROM public.coupons c
  WHERE c.id = p_coupon_id;

  IF NOT FOUND THEN
    RETURN 'كود الخصم غير صحيح';
  END IF;

  IF v_coupon.active IS NOT TRUE THEN
    RETURN 'كود الخصم غير مفعّل';
  END IF;

  IF v_coupon.starts_at IS NOT NULL AND now() < v_coupon.starts_at THEN
    RETURN 'الكود لم يبدأ بعد';
  END IF;

  IF v_coupon.expires_at IS NOT NULL AND now() > v_coupon.expires_at THEN
    RETURN 'كود الخصم منتهي';
  END IF;

  IF v_coupon.usage_limit IS NOT NULL AND v_coupon.used_count >= v_coupon.usage_limit THEN
    RETURN 'تم الوصول للحد الأقصى لاستخدام الكود';
  END IF;

  IF coalesce(p_subtotal, 0) < coalesce(v_coupon.min_order, 0) THEN
    RETURN 'قيمة الطلب أقل من الحد الأدنى للكود';
  END IF;

  IF v_coupon.discount_value <= 0 AND v_coupon.free_shipping IS NOT TRUE THEN
    RETURN 'الكود لا يحتوي على خصم أو شحن مجاني';
  END IF;

  IF v_phone IS NULL AND p_customer_user_id IS NULL THEN
    RETURN 'أدخلي رقم الهاتف قبل استخدام الكوبون';
  END IF;

  IF v_coupon.audience_mode = 'single_customer' AND EXISTS (
    SELECT 1
    FROM public.coupon_redemptions r
    WHERE r.coupon_id = p_coupon_id
      AND NOT (
        (v_phone IS NOT NULL AND r.phone_normalized = v_phone)
        OR (p_customer_user_id IS NOT NULL AND r.customer_user_id = p_customer_user_id)
      )
  ) THEN
    RETURN 'هذا الكوبون مخصص لعميل واحد وقد تم ربطه بعميل آخر';
  END IF;

  IF v_coupon.per_customer_limit IS NOT NULL THEN
    SELECT count(*)::integer INTO v_customer_uses
    FROM public.coupon_redemptions r
    WHERE r.coupon_id = p_coupon_id
      AND (
        (v_phone IS NOT NULL AND r.phone_normalized = v_phone)
        OR (p_customer_user_id IS NOT NULL AND r.customer_user_id = p_customer_user_id)
      );

    IF v_customer_uses >= v_coupon.per_customer_limit THEN
      RETURN 'وصلتِ إلى الحد المسموح لاستخدام هذا الكوبون بهذا الرقم';
    END IF;
  END IF;

  IF v_coupon.first_order_only IS TRUE AND EXISTS (
    SELECT 1
    FROM public.orders o
    WHERE o.id IS DISTINCT FROM p_exclude_order_id
      AND (
        (p_customer_user_id IS NOT NULL AND o.user_id = p_customer_user_id)
        OR (
          v_phone IS NOT NULL
          AND private.normalize_egypt_phone(o.phone) = v_phone
        )
      )
      AND lower(coalesce(o.status, '')) NOT IN ('ملغي', 'ملغى', 'cancelled', 'canceled')
  ) THEN
    RETURN 'هذا الكوبون متاح لأول طلب فقط، ويوجد طلب سابق لهذا الرقم أو الحساب';
  END IF;

  RETURN NULL;
END;
$function$;

REVOKE ALL ON FUNCTION private.coupon_customer_validation_message(uuid, numeric, text, uuid, uuid)
  FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.validate_coupon(
  p_code text,
  p_subtotal numeric,
  p_phone text
)
RETURNS TABLE(
  valid boolean,
  id uuid,
  code text,
  discount_type text,
  discount_value numeric,
  max_discount numeric,
  free_shipping boolean,
  message text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_coupon public.coupons%ROWTYPE;
  v_message text;
BEGIN
  SELECT * INTO v_coupon
  FROM public.coupons c
  WHERE upper(trim(c.code)) = upper(trim(coalesce(p_code, '')))
     OR c.id::text = trim(coalesce(p_code, ''))
  LIMIT 1;

  IF NOT FOUND THEN
    RETURN QUERY SELECT false, NULL::uuid, NULL::text, NULL::text,
      NULL::numeric, NULL::numeric, false, 'كود الخصم غير صحيح'::text;
    RETURN;
  END IF;

  v_message := private.coupon_customer_validation_message(
    v_coupon.id, p_subtotal, p_phone, auth.uid(), NULL
  );

  RETURN QUERY SELECT
    (v_message IS NULL),
    v_coupon.id,
    v_coupon.code,
    v_coupon.discount_type,
    v_coupon.discount_value,
    v_coupon.max_discount,
    coalesce(v_coupon.free_shipping, false),
    coalesce(v_message, 'تم التحقق من الكوبون');
END;
$function$;

-- Keep the older two-argument RPC working for older app versions. It cannot bypass
-- the order-insert enforcement trigger below.
CREATE OR REPLACE FUNCTION public.validate_coupon(
  p_code text,
  p_subtotal numeric
)
RETURNS TABLE(
  valid boolean,
  id uuid,
  code text,
  discount_type text,
  discount_value numeric,
  max_discount numeric,
  free_shipping boolean,
  message text
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $function$
  SELECT * FROM public.validate_coupon(p_code, p_subtotal, NULL::text);
$function$;

REVOKE ALL ON FUNCTION public.validate_coupon(text, numeric, text) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.validate_coupon(text, numeric) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.validate_coupon(text, numeric, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.validate_coupon(text, numeric) TO anon, authenticated;

CREATE OR REPLACE FUNCTION private.apply_coupon_to_new_order()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_coupon public.coupons%ROWTYPE;
  v_phone text;
  v_user_id uuid;
  v_message text;
  v_discount numeric := 0;
  v_shipping numeric := 0;
  v_prime_fee numeric := 300;
  v_total numeric := 0;
  v_coupon_free_shipping boolean := false;
BEGIN
  IF NULLIF(trim(coalesce(NEW.coupon_code, '')), '') IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT * INTO v_coupon
  FROM public.coupons c
  WHERE upper(trim(c.code)) = upper(trim(NEW.coupon_code))
     OR c.id::text = trim(NEW.coupon_code)
  LIMIT 1
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'كود الخصم غير صحيح أو لم يعد متاحًا';
  END IF;

  v_phone := private.normalize_egypt_phone(NEW.phone);
  v_user_id := coalesce(NEW.user_id, auth.uid());

  v_message := private.coupon_customer_validation_message(
    v_coupon.id,
    NEW.subtotal,
    NEW.phone,
    v_user_id,
    NEW.id
  );

  IF v_message IS NOT NULL THEN
    RAISE EXCEPTION '%', v_message;
  END IF;

  IF v_coupon.discount_type = 'percent' THEN
    v_discount := coalesce(NEW.subtotal, 0) * (v_coupon.discount_value / 100.0);
  ELSIF v_coupon.discount_type = 'fixed' THEN
    v_discount := v_coupon.discount_value;
  ELSE
    RAISE EXCEPTION 'نوع الخصم المخزن غير مدعوم';
  END IF;

  IF v_coupon.max_discount IS NOT NULL AND v_coupon.max_discount > 0 THEN
    v_discount := least(v_discount, v_coupon.max_discount);
  END IF;
  v_discount := greatest(0, least(v_discount, coalesce(NEW.subtotal, 0)));

  v_shipping := coalesce(NEW.shipping_cost, 0);
  v_coupon_free_shipping := coalesce(v_coupon.free_shipping, false)
    AND NOT coalesce(NEW.prime_free_shipping, false);
  IF v_coupon_free_shipping THEN
    v_shipping := 0;
  END IF;

  BEGIN
    SELECT coalesce(nullif(sc.config->'prime'->>'price', '')::numeric, 300)
      INTO v_prime_fee
    FROM public.site_customizations sc
    WHERE sc.id = 1;
  EXCEPTION WHEN invalid_text_representation THEN
    v_prime_fee := 300;
  END;

  v_total := greatest(
    0,
    coalesce(NEW.subtotal, 0)
      + v_shipping
      + CASE WHEN coalesce(NEW.prime_requested, false) THEN coalesce(v_prime_fee, 300) ELSE 0 END
      - v_discount
      - coalesce(NEW.prime_discount, 0)
  );

  UPDATE public.orders
  SET coupon_discount = v_discount,
      coupon_free_shipping = v_coupon_free_shipping,
      shipping_cost = v_shipping,
      total = v_total,
      coupon_redeemed_at = now()
  WHERE id = NEW.id;

  INSERT INTO public.coupon_redemptions (
    coupon_id, order_id, phone_normalized, customer_user_id
  )
  VALUES (v_coupon.id, NEW.id, v_phone, v_user_id);

  UPDATE public.coupons
  SET used_count = used_count + 1
  WHERE id = v_coupon.id;

  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.apply_coupon_to_new_order() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_elory_apply_coupon_to_new_order ON public.orders;
CREATE TRIGGER trg_elory_apply_coupon_to_new_order
AFTER INSERT ON public.orders
FOR EACH ROW
WHEN (NEW.coupon_code IS NOT NULL AND length(trim(NEW.coupon_code)) > 0)
EXECUTE FUNCTION private.apply_coupon_to_new_order();

-- This RPC now only confirms the use already committed atomically by the order trigger.
-- It intentionally does not increment used_count a second time.
CREATE OR REPLACE FUNCTION public.redeem_coupon(
  p_coupon_id uuid,
  p_order_id uuid DEFAULT NULL::uuid,
  p_access_token text DEFAULT NULL::text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_order public.orders%ROWTYPE;
  v_authorized boolean := false;
BEGIN
  IF p_coupon_id IS NULL OR p_order_id IS NULL THEN
    RETURN false;
  END IF;

  SELECT * INTO v_order
  FROM public.orders o
  WHERE o.id = p_order_id;

  IF NOT FOUND THEN
    RETURN false;
  END IF;

  v_authorized := (
    auth.uid() IS NOT NULL AND v_order.user_id = auth.uid()
  ) OR (
    p_access_token IS NOT NULL
    AND length(trim(p_access_token)) >= 24
    AND v_order.customer_access_token = p_access_token
  );

  IF NOT v_authorized THEN
    RETURN false;
  END IF;

  RETURN EXISTS (
    SELECT 1
    FROM public.coupon_redemptions r
    WHERE r.order_id = p_order_id
      AND r.coupon_id = p_coupon_id
      AND v_order.coupon_redeemed_at IS NOT NULL
  );
END;
$function$;

REVOKE ALL ON FUNCTION public.redeem_coupon(uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.redeem_coupon(uuid, uuid, text) TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
