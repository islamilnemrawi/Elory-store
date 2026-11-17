-- Treat legacy generic "new" online-payment rows as unverified until a trusted Paymob confirmation.
CREATE OR REPLACE FUNCTION private.enforce_paid_order_confirmation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
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
        'جديد',
        'طلب جديد',
        'تم تأكيد الطلب',
        'قيد التجهيز',
        'جاري التجهيز',
        'تم الشحن',
        'تم التسليم'
    );
    v_was_unconfirmed := lower(v_old_status) IN (
        'جديد',
        'جاري التأكيد',
        'pending',
        'new',
        'جاري الدفع',
        'فشل الدفع',
        'فشل إنشاء الدفع',
        'payment pending',
        'pending payment',
        'payment failed',
        'failed payment',
        'failed to create payment'
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

REVOKE ALL ON FUNCTION private.enforce_paid_order_confirmation() FROM PUBLIC, anon, authenticated;
