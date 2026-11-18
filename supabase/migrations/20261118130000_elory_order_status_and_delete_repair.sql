-- Fix the confirmed order-delete failure and align the confirmed-payment state.
-- No customer/order/product records are modified by this migration.

CREATE OR REPLACE FUNCTION public.admin_delete_selected_data(
    p_pin text,
    p_scope text,
    p_ids text[] DEFAULT NULL::text[]
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
    v_owner_id uuid;
    v_pin_hash text;
    v_failed_attempts smallint;
    v_locked_until timestamptz;
    v_scope text := lower(trim(coalesce(p_scope, '')));
    v_deleted integer := 0;
    v_order_sequence_reset boolean := false;
    v_order_sequence text;
BEGIN
    SELECT s.owner_id, s.pin_hash, s.failed_attempts, s.locked_until
      INTO v_owner_id, v_pin_hash, v_failed_attempts, v_locked_until
      FROM public.owner_data_reset_settings s
     WHERE s.singleton IS TRUE
     FOR UPDATE;

    IF auth.uid() IS NULL OR auth.uid() IS DISTINCT FROM v_owner_id THEN
        RETURN jsonb_build_object('success', false, 'code', 'forbidden',
                                  'message', 'حذف البيانات متاح للمالك الأساسي فقط');
    END IF;
    IF v_pin_hash IS NULL THEN
        RETURN jsonb_build_object('success', false, 'code', 'pin_not_configured',
                                  'message', 'يجب إعداد رمز PIN من 6 أرقام أولاً');
    END IF;
    IF v_locked_until IS NOT NULL AND v_locked_until > now() THEN
        RETURN jsonb_build_object('success', false, 'code', 'pin_locked',
                                  'message', 'تم إيقاف المحاولة مؤقتًا بسبب تكرار الرمز الخاطئ');
    END IF;

    IF coalesce(p_pin, '') !~ '^[0-9]{6}$'
       OR extensions.crypt(p_pin, v_pin_hash) IS DISTINCT FROM v_pin_hash THEN
        v_failed_attempts := least(coalesce(v_failed_attempts, 0) + 1, 5);
        UPDATE public.owner_data_reset_settings
           SET failed_attempts = v_failed_attempts,
               locked_until = CASE WHEN v_failed_attempts >= 5 THEN now() + interval '15 minutes' ELSE NULL END,
               updated_at = now()
         WHERE singleton IS TRUE;
        RETURN jsonb_build_object(
            'success', false,
            'code', CASE WHEN v_failed_attempts >= 5 THEN 'pin_locked' ELSE 'invalid_pin' END,
            'attempts_remaining', greatest(0, 5 - v_failed_attempts),
            'message', CASE WHEN v_failed_attempts >= 5
                THEN 'تم إيقاف المحاولات لمدة 15 دقيقة' ELSE 'رمز PIN غير صحيح' END
        );
    END IF;

    UPDATE public.owner_data_reset_settings
       SET failed_attempts = 0, locked_until = NULL, updated_at = now()
     WHERE singleton IS TRUE;

    IF v_scope NOT IN ('orders', 'customers', 'coupons', 'products', 'prime') THEN
        RETURN jsonb_build_object('success', false, 'code', 'invalid_scope',
                                  'message', 'نوع البيانات المطلوب حذفه غير مسموح');
    END IF;
    IF p_ids IS NOT NULL AND cardinality(p_ids) = 0 THEN
        RETURN jsonb_build_object('success', false, 'code', 'empty_selection',
                                  'message', 'لم يتم تحديد أي سجلات للحذف');
    END IF;

    IF v_scope = 'orders' THEN
        LOCK TABLE public.orders IN ACCESS EXCLUSIVE MODE;
        DELETE FROM public.orders o
         WHERE p_ids IS NULL OR o.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;

        IF NOT EXISTS (SELECT 1 FROM public.orders) THEN
            v_order_sequence := pg_get_serial_sequence('public.orders', 'order_number');
            IF v_order_sequence IS NULL THEN
                RAISE EXCEPTION 'Could not resolve orders.order_number identity sequence';
            END IF;
            EXECUTE format('ALTER SEQUENCE %s RESTART WITH 1', v_order_sequence::regclass);
            v_order_sequence_reset := true;
        END IF;

        -- PostgREST's safe-update guard requires an explicit WHERE clause,
        -- even for a full reconciliation. id is the coupons primary key.
        UPDATE public.coupons c
           SET used_count = (
               SELECT count(*)::integer
                 FROM public.coupon_redemptions cr
                WHERE cr.coupon_id = c.id
           )
         WHERE c.id IS NOT NULL;

    ELSIF v_scope = 'customers' THEN
        DELETE FROM public.customers c
         WHERE p_ids IS NULL OR c.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    ELSIF v_scope = 'coupons' THEN
        DELETE FROM public.coupon_redemptions cr
         WHERE p_ids IS NULL OR cr.coupon_id::text = ANY(p_ids);
        DELETE FROM public.coupons c
         WHERE p_ids IS NULL OR c.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    ELSIF v_scope = 'products' THEN
        DELETE FROM public.products p
         WHERE p_ids IS NULL OR p.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    ELSIF v_scope = 'prime' THEN
        DELETE FROM public.prime_subscriptions ps
         WHERE p_ids IS NULL OR ps.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    END IF;

    INSERT INTO public.owner_data_reset_audit(
        owner_id, scope, selected_ids, deleted_count, order_sequence_reset
    ) VALUES (v_owner_id, v_scope, p_ids, v_deleted, v_order_sequence_reset);

    RETURN jsonb_build_object(
        'success', true, 'scope', v_scope, 'deleted_count', v_deleted,
        'order_sequence_reset', v_order_sequence_reset,
        'message', CASE v_scope
            WHEN 'orders' THEN 'تم حذف الطلبات المحددة بنجاح'
            WHEN 'customers' THEN 'تم حذف العملاء المحددين بنجاح'
            WHEN 'products' THEN 'تم حذف المنتجات المحددة بنجاح'
            WHEN 'prime' THEN 'تم حذف اشتراكات Elory Prime المحددة بنجاح'
            ELSE 'تم حذف الكوبونات المحددة بنجاح'
        END
    );
END;
$function$;

CREATE OR REPLACE FUNCTION private.elora_notify_new_order()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'private'
AS $function$
DECLARE
    v_url text;
    v_secret text;
    v_request_id bigint;
    v_method text := lower(trim(coalesce(NEW.payment_method, '')));
    v_status text := trim(coalesce(NEW.status, ''));
    v_old_status text := CASE WHEN TG_OP = 'UPDATE' THEN trim(coalesce(OLD.status, '')) ELSE '' END;
    v_should_notify boolean := false;
BEGIN
    IF v_method IN ('cash_on_delivery', 'cash', 'cod', 'الدفع عند الاستلام')
       AND v_status = 'جاري التأكيد' THEN
        v_should_notify := true;
    ELSIF v_method IN ('card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash')
       AND v_status = 'جاري التحضير'
       AND (TG_OP = 'INSERT' OR v_old_status IS DISTINCT FROM v_status) THEN
        v_should_notify := true;
    END IF;

    IF NOT v_should_notify THEN RETURN NEW; END IF;

    SELECT webhook_url, webhook_secret
      INTO v_url, v_secret
      FROM private.elora_push_config
     WHERE id = 1 AND enabled = true;
    IF v_url IS NULL OR v_secret IS NULL THEN RETURN NEW; END IF;

    SELECT net.http_post(
        url := v_url,
        body := jsonb_build_object(
            'record', to_jsonb(NEW), 'type', 'INSERT', 'table', 'orders', 'schema', 'public'
        ),
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'X-Elora-Webhook-Secret', v_secret
        )
    ) INTO v_request_id;

    RETURN NEW;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'Elora Push trigger failed: %', SQLERRM;
    RETURN NEW;
END;
$function$;

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
  IF NULLIF(btrim(coalesce(NEW.coupon_code, '')), '') IS NULL THEN RETURN NEW; END IF;

  v_phone := private.normalize_egypt_phone(NEW.phone);
  v_user_id := coalesce(NEW.user_id, auth.uid());
  v_online_payment := lower(btrim(coalesce(NEW.payment_method, ''))) IN (
    'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
  );
  v_confirmed_online := v_online_payment
    AND lower(btrim(coalesce(NEW.status, ''))) = 'جاري التحضير';

  IF TG_OP = 'UPDATE' THEN
    IF NOT v_confirmed_online
       OR lower(btrim(coalesce(OLD.status, ''))) = 'جاري التحضير' THEN
      RETURN NEW;
    END IF;
    IF NEW.coupon_redeemed_at IS NOT NULL OR EXISTS (
      SELECT 1 FROM public.coupon_redemptions cr WHERE cr.order_id = NEW.id
    ) THEN RETURN NEW; END IF;
  END IF;

  SELECT * INTO v_coupon
    FROM public.coupons c
   WHERE upper(btrim(c.code)) = upper(btrim(NEW.coupon_code))
      OR c.id::text = btrim(NEW.coupon_code)
   LIMIT 1 FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'كود الخصم غير صحيح أو لم يعد متاحًا'; END IF;

  IF TG_OP = 'INSERT' THEN
    v_message := private.coupon_customer_validation_message(
      v_coupon.id, NEW.subtotal, NEW.phone, v_user_id, NEW.id
    );
    IF v_message IS NOT NULL THEN RAISE EXCEPTION '%', v_message; END IF;
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
  IF v_coupon_free_shipping THEN v_shipping := 0; END IF;

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
    coalesce(NEW.subtotal, 0) + v_shipping
      + CASE WHEN coalesce(NEW.prime_requested, false) THEN coalesce(v_prime_fee, 300) ELSE 0 END
      - v_discount
  );

  v_should_redeem := NOT v_online_payment OR v_confirmed_online;

  UPDATE public.orders
     SET coupon_discount = v_discount,
         coupon_free_shipping = v_coupon_free_shipping,
         shipping_cost = v_shipping,
         total = round(v_total, 2),
         profit = CASE WHEN NEW.profit IS NULL THEN NULL ELSE round(NEW.profit - v_discount, 2) END,
         coupon_redeemed_at = CASE WHEN v_should_redeem THEN now() ELSE coupon_redeemed_at END
   WHERE id = NEW.id;

  IF v_should_redeem THEN
    INSERT INTO public.coupon_redemptions(coupon_id, order_id, phone_normalized, customer_user_id)
    VALUES (v_coupon.id, NEW.id, v_phone, v_user_id)
    ON CONFLICT (order_id) DO NOTHING;
    IF FOUND THEN
      UPDATE public.coupons SET used_count = used_count + 1 WHERE id = v_coupon.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.admin_delete_selected_data(text, text, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_delete_selected_data(text, text, text[]) TO authenticated;
NOTIFY pgrst, 'reload schema';