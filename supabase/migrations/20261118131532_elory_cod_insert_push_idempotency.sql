-- Send COD new-order push only once, at insert time.
-- Online orders are still announced only when Paymob promotes them to preparation.
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
       AND v_status = 'جاري التأكيد'
       AND TG_OP = 'INSERT' THEN
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
            'record', to_jsonb(NEW),
            'type', TG_OP,
            'table', 'orders',
            'schema', 'public'
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

NOTIFY pgrst, 'reload schema';
