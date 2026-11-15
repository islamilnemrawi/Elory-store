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

NOTIFY pgrst, 'reload schema';
