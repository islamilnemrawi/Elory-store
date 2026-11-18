-- Owner-only product cleanup and the three customer-facing fulfillment states.
-- This migration changes function definitions and an audit constraint only; it deletes no data.

ALTER TABLE public.owner_data_reset_audit
    DROP CONSTRAINT IF EXISTS owner_data_reset_audit_scope_check;

ALTER TABLE public.owner_data_reset_audit
    ADD CONSTRAINT owner_data_reset_audit_scope_check
    CHECK (scope = ANY (ARRAY['orders'::text, 'customers'::text, 'coupons'::text, 'products'::text]));

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

    IF v_scope NOT IN ('orders', 'customers', 'coupons', 'products') THEN
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

        -- order_items and coupon_redemptions cascade; Prime order_id is SET NULL.
        IF NOT EXISTS (SELECT 1 FROM public.orders) THEN
            ALTER SEQUENCE public.elora_order_number_seq RESTART WITH 1;
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
        -- Product images remain in Storage so shared/reused assets are never removed accidentally.
        DELETE FROM public.products p
         WHERE p_ids IS NULL OR p.id::text = ANY(p_ids);
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
            ELSE 'تم حذف الكوبونات المحددة بنجاح'
        END
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
    r public.orders%ROWTYPE;
BEGIN
    IF NOT public.has_staff_permission('orders.edit') THEN
        RAISE EXCEPTION 'ليس لديك صلاحية تعديل الطلبات';
    END IF;

    IF trim(coalesce(p_status, '')) NOT IN (
        'جديد', 'طلب جديد', 'جاري التأكيد', 'تم التأكيد',
        'جاري التجهيز', 'قيد التجهيز', 'جاري التحضير',
        'تم الشحن', 'جاري الشحن', 'تم التسليم', 'ملغي'
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

CREATE OR REPLACE FUNCTION private.enforce_paid_order_confirmation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
    v_method text := lower(btrim(coalesce(NEW.payment_method, '')));
    v_old_method text := CASE WHEN TG_OP = 'UPDATE' THEN lower(btrim(coalesce(OLD.payment_method, ''))) ELSE '' END;
    v_role text := coalesce(auth.role(), '');
    v_old_status text := CASE WHEN TG_OP = 'UPDATE' THEN btrim(coalesce(OLD.status, '')) ELSE '' END;
    v_new_status text := btrim(coalesce(NEW.status, ''));
    v_online_method boolean;
    v_old_online_method boolean;
    v_final_status boolean;
    v_was_unconfirmed boolean;
BEGIN
    v_online_method := v_method IN ('card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash');
    v_old_online_method := v_old_method IN ('card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash');
    v_final_status := v_new_status IN (
        'جديد', 'طلب جديد', 'تم تأكيد الطلب', 'قيد التجهيز',
        'جاري التجهيز', 'جاري التحضير', 'جاري الشحن', 'تم الشحن', 'تم التسليم'
    );
    v_was_unconfirmed := lower(v_old_status) IN (
        'جديد', 'جاري التأكيد', 'pending', 'new', 'جاري الدفع',
        'فشل الدفع', 'فشل إنشاء الدفع', 'payment pending', 'pending payment',
        'payment failed', 'failed payment', 'failed to create payment'
    );

    IF v_online_method THEN
        IF TG_OP = 'INSERT' AND v_role <> 'service_role' THEN
            RAISE EXCEPTION 'طلبات الدفع الإلكتروني يجب إنشاؤها عبر بوابة Paymob الآمنة'
                USING ERRCODE = '42501';
        END IF;

        IF TG_OP = 'UPDATE'
           AND v_final_status
           AND (NOT v_old_online_method OR v_was_unconfirmed)
           AND v_role <> 'service_role' THEN
            RAISE EXCEPTION 'تأكيد طلب الدفع الإلكتروني متاح فقط بعد تحقق Paymob من الدفع'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION public.admin_delete_selected_data(text, text, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_delete_selected_data(text, text, text[]) TO authenticated;
REVOKE ALL ON FUNCTION public.admin_update_order_status(uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_update_order_status(uuid, text) TO authenticated;
