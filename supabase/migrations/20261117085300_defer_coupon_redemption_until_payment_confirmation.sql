-- Defer coupon redemption until an online payment is confirmed.
-- Coupon validation and price calculation still happen on the pending order so Paymob
-- receives the correct discounted amount. Usage is consumed only after confirmed payment.
CREATE OR REPLACE FUNCTION private.apply_coupon_to_new_order()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
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
  v_online_payment boolean := false;
  v_confirmed_online boolean := false;
  v_should_redeem boolean := false;
BEGIN
  IF NULLIF(btrim(coalesce(NEW.coupon_code, '')), '') IS NULL THEN
    RETURN NEW;
  END IF;

  v_phone := private.normalize_egypt_phone(NEW.phone);
  v_user_id := coalesce(NEW.user_id, auth.uid());
  v_online_payment := lower(btrim(coalesce(NEW.payment_method, ''))) IN (
    'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
  );
  v_confirmed_online := v_online_payment
    AND lower(btrim(coalesce(NEW.status, ''))) = 'طلب جديد';

  -- On status updates, only the first trusted transition to a confirmed online
  -- order may consume a coupon. Repeated status updates are idempotent.
  IF TG_OP = 'UPDATE' THEN
    IF NOT v_confirmed_online
       OR lower(btrim(coalesce(OLD.status, ''))) = 'طلب جديد' THEN
      RETURN NEW;
    END IF;

    IF NEW.coupon_redeemed_at IS NOT NULL OR EXISTS (
      SELECT 1 FROM public.coupon_redemptions cr WHERE cr.order_id = NEW.id
    ) THEN
      RETURN NEW;
    END IF;
  END IF;

  SELECT * INTO v_coupon
  FROM public.coupons c
  WHERE upper(btrim(c.code)) = upper(btrim(NEW.coupon_code))
     OR c.id::text = btrim(NEW.coupon_code)
  LIMIT 1
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'كود الخصم غير صحيح أو لم يعد متاحًا';
  END IF;

  -- The attempt was validated when it was first created. Revalidate only on INSERT.
  -- Rechecking at callback time could reject a payment that Paymob already captured.
  IF TG_OP = 'INSERT' THEN
    v_message := private.coupon_customer_validation_message(
      v_coupon.id, NEW.subtotal, NEW.phone, v_user_id, NEW.id
    );
    IF v_message IS NOT NULL THEN
      RAISE EXCEPTION '%', v_message;
    END IF;
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
  v_discount := round(greatest(0, least(v_discount, coalesce(NEW.subtotal, 0))), 2);

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

  v_should_redeem := NOT v_online_payment OR v_confirmed_online;

  UPDATE public.orders
  SET coupon_discount = v_discount,
      coupon_free_shipping = v_coupon_free_shipping,
      shipping_cost = v_shipping,
      total = round(v_total, 2),
      profit = CASE
        WHEN NEW.profit IS NULL THEN NULL
        ELSE round(NEW.profit - v_discount, 2)
      END,
      coupon_redeemed_at = CASE WHEN v_should_redeem THEN now() ELSE coupon_redeemed_at END
  WHERE id = NEW.id;

  IF v_should_redeem THEN
    INSERT INTO public.coupon_redemptions (
      coupon_id, order_id, phone_normalized, customer_user_id
    )
    VALUES (v_coupon.id, NEW.id, v_phone, v_user_id)
    ON CONFLICT (order_id) DO NOTHING;

    IF FOUND THEN
      UPDATE public.coupons
      SET used_count = used_count + 1
      WHERE id = v_coupon.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_elory_apply_coupon_to_new_order ON public.orders;
CREATE TRIGGER trg_elory_apply_coupon_to_new_order
AFTER INSERT OR UPDATE OF status ON public.orders
FOR EACH ROW
WHEN (NEW.coupon_code IS NOT NULL AND length(btrim(NEW.coupon_code)) > 0)
EXECUTE FUNCTION private.apply_coupon_to_new_order();

REVOKE ALL ON FUNCTION private.apply_coupon_to_new_order() FROM PUBLIC, anon, authenticated;


-- Customer order history must not show pending, failed, or legacy-unverified online attempts.
CREATE OR REPLACE FUNCTION public.get_customer_orders(
  p_access_token text DEFAULT NULL::text,
  p_phone text DEFAULT NULL::text
)
RETURNS TABLE(
  id uuid,
  order_number text,
  user_id uuid,
  created_at timestamp with time zone,
  status text,
  items jsonb,
  shipping_cost numeric,
  total numeric,
  governorate text,
  center text,
  customer_order_code text
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
  SELECT
    o.id,
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text) AS order_number,
    o.user_id,
    o.created_at,
    o.status,
    CASE
      WHEN jsonb_typeof(o.items) = 'array' THEN
        coalesce((
          SELECT jsonb_agg(
            x.item
              - 'wholesale_price'
              - 'product_code'
              - 'product_image'
              - 'product_name'
              - 'wholesalePrice'
              - 'productCode'
              - 'productImage'
              - 'productName'
            ORDER BY x.ordinality
          )
          FROM jsonb_array_elements(o.items) WITH ORDINALITY AS x(item, ordinality)
        ), '[]'::jsonb)
      ELSE coalesce(o.items, '[]'::jsonb)
    END AS items,
    coalesce(o.shipping_cost, 0) AS shipping_cost,
    coalesce(o.total, 0) AS total,
    o.governorate,
    o.center,
    o.customer_order_code
  FROM public.orders AS o
  WHERE (
    (auth.uid() IS NOT NULL AND o.user_id = auth.uid())
    OR (
      p_access_token IS NOT NULL
      AND length(btrim(p_access_token)) >= 24
      AND o.customer_access_token = btrim(p_access_token)
    )
  )
    AND lower(btrim(coalesce(o.status, ''))) NOT IN (
      'جاري الدفع',
      'فشل الدفع',
      'فشل إنشاء الدفع',
      'payment pending',
      'pending payment',
      'payment failed',
      'failed payment',
      'failed to create payment'
    )
    AND NOT (
      lower(btrim(coalesce(o.payment_method, ''))) IN (
        'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
      )
      AND lower(btrim(coalesce(o.status, ''))) IN (
        'جديد', 'جاري التأكيد', 'pending', 'new'
      )
    )
  ORDER BY o.created_at DESC;
$function$;

NOTIFY pgrst, 'reload schema';
