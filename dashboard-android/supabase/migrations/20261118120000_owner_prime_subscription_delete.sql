ALTER TABLE public.owner_data_reset_audit
    DROP CONSTRAINT IF EXISTS owner_data_reset_audit_scope_check;

ALTER TABLE public.owner_data_reset_audit
    ADD CONSTRAINT owner_data_reset_audit_scope_check
    CHECK (scope = ANY (ARRAY['orders'::text, 'customers'::text, 'coupons'::text, 'products'::text, 'prime'::text]));

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
            'message', CASE
                WHEN v_failed_attempts >= 5 THEN 'تم إيقاف المحاولات لمدة 15 دقيقة'
                ELSE 'رمز PIN غير صحيح'
            END
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

        -- Reset only the internal dashboard serial when no orders remain.
        -- customer_order_code is a separate random, immutable customer-facing token.
        IF NOT EXISTS (SELECT 1 FROM public.orders) THEN
            v_order_sequence := pg_get_serial_sequence('public.orders', 'order_number');
            IF v_order_sequence IS NULL THEN
                RAISE EXCEPTION 'Could not resolve orders.order_number identity sequence';
            END IF;
            EXECUTE format('ALTER SEQUENCE %s RESTART WITH 1', v_order_sequence::regclass);
            v_order_sequence_reset := true;
        END IF;

        UPDATE public.coupons c
           SET used_count = (
               SELECT count(*)::integer
                 FROM public.coupon_redemptions cr
                WHERE cr.coupon_id = c.id
           );
    ELSIF v_scope = 'customers' THEN
        -- Delete customer profile rows only; never delete Auth accounts or order history.
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
        -- Keep Storage images; shared assets may be reused by other records.
        DELETE FROM public.products p
         WHERE p_ids IS NULL OR p.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    ELSIF v_scope = 'prime' THEN
        -- Remove subscription records only. Preserve Auth users, customer profiles and orders.
        DELETE FROM public.prime_subscriptions ps
         WHERE p_ids IS NULL OR ps.id::text = ANY(p_ids);
        GET DIAGNOSTICS v_deleted = ROW_COUNT;
    END IF;

    INSERT INTO public.owner_data_reset_audit(
        owner_id, scope, selected_ids, deleted_count, order_sequence_reset
    ) VALUES (v_owner_id, v_scope, p_ids, v_deleted, v_order_sequence_reset);

    RETURN jsonb_build_object(
        'success', true,
        'scope', v_scope,
        'deleted_count', v_deleted,
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