-- Keep Paymob's pre-payment price/stock validation row, but never expose or notify it as a confirmed order.
-- Only trusted server callbacks may create or promote electronic-payment orders.
CREATE OR REPLACE FUNCTION private.enforce_paid_order_confirmation()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
    v_method text := lower(trim(coalesce(NEW.payment_method, '')));
    v_role text := coalesce(auth.role(), '');
    v_final_status boolean := trim(coalesce(NEW.status, '')) IN (
        'جديد',
        'طلب جديد',
        'تم تأكيد الطلب',
        'قيد التجهيز',
        'جاري التجهيز',
        'تم الشحن',
        'تم التسليم'
    );
BEGIN
    IF v_method IN ('card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash') THEN
        IF TG_OP = 'INSERT' AND v_role <> 'service_role' THEN
            RAISE EXCEPTION 'طلبات الدفع الإلكتروني يجب إنشاؤها عبر بوابة Paymob الآمنة'
                USING ERRCODE = '42501';
        END IF;

        IF TG_OP = 'UPDATE'
           AND v_final_status
           AND trim(coalesce(OLD.status, '')) IS DISTINCT FROM trim(coalesce(NEW.status, ''))
           AND v_role <> 'service_role' THEN
            RAISE EXCEPTION 'تأكيد طلب الدفع الإلكتروني متاح فقط بعد تحقق Paymob من الدفع'
                USING ERRCODE = '42501';
        END IF;
    END IF;

    RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.enforce_paid_order_confirmation() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS elory_enforce_paid_order_confirmation ON public.orders;
CREATE TRIGGER elory_enforce_paid_order_confirmation
BEFORE INSERT OR UPDATE OF status, payment_method
ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.enforce_paid_order_confirmation();


-- A new-order notification is generated only for COD orders accepted at checkout,
-- or when a Paymob-pending order is promoted to its confirmed state.
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
    v_old_status text := CASE
        WHEN TG_OP = 'UPDATE' THEN trim(coalesce(OLD.status, ''))
        ELSE ''
    END;
    v_should_notify boolean := false;
BEGIN
    IF v_method IN ('cash_on_delivery', 'cash', 'cod', 'الدفع عند الاستلام')
       AND v_status = 'جديد' THEN
        v_should_notify := true;
    ELSIF v_method IN ('card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash')
       AND v_status = 'طلب جديد'
       AND (TG_OP = 'INSERT' OR v_old_status IS DISTINCT FROM v_status) THEN
        v_should_notify := true;
    END IF;

    IF NOT v_should_notify THEN
        RETURN NEW;
    END IF;

    SELECT webhook_url, webhook_secret
      INTO v_url, v_secret
      FROM private.elora_push_config
     WHERE id = 1
       AND enabled = true;

    IF v_url IS NULL OR v_secret IS NULL THEN
        RETURN NEW;
    END IF;

    -- Keep the existing webhook envelope for compatibility with the deployed push receiver.
    SELECT net.http_post(
        url := v_url,
        body := jsonb_build_object(
            'record', to_jsonb(NEW),
            'type', 'INSERT',
            'table', 'orders',
            'schema', 'public'
        ),
        headers := jsonb_build_object(
            'Content-Type', 'application/json',
            'X-Elora-Webhook-Secret', v_secret
        )
    )
    INTO v_request_id;

    RETURN NEW;
EXCEPTION
    WHEN OTHERS THEN
        RAISE WARNING 'Elora Push trigger failed: %', SQLERRM;
        RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS elora_new_order_push ON public.orders;
CREATE TRIGGER elora_new_order_push
AFTER INSERT OR UPDATE OF status
ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.elora_notify_new_order();
