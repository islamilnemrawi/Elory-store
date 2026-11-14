BEGIN;

DO $$
DECLARE
  v_product_id uuid;
  v_suffix text := replace(gen_random_uuid()::text, '-', '');
  v_governorate text;
  v_center text;
  v_payload jsonb;
  v_key uuid := gen_random_uuid();
  v_order_id uuid;
  v_replay_id uuid;
  v_result jsonb;
  v_stock integer;
  v_reservations integer;
  v_session jsonb;
BEGIN
  SELECT g.governorate,
         COALESCE((
           SELECT c.center
             FROM public.shipping_centers c
            WHERE c.governorate = g.governorate
              AND c.active IS TRUE
            ORDER BY c.center
            LIMIT 1
         ), '')
    INTO v_governorate, v_center
    FROM public.shipping_governorates g
   WHERE g.active IS TRUE
   ORDER BY CASE WHEN g.centers_enabled IS FALSE THEN 0 ELSE 1 END, g.governorate
   LIMIT 1;

  IF v_governorate IS NULL THEN
    RAISE EXCEPTION 'No active shipping governorate exists in the local schema snapshot.';
  END IF;

  INSERT INTO public.products (
    name, description, image, category, price, old_price, wholesale_price,
    code, stock, discount, featured, active, created_at,
    colors, sizes, variants, sku, weight, gallery, color_options
  )
  VALUES (
    'Elory SQL Integration Fixture', 'Synthetic local test product',
    'https://placehold.co/320x320/webp?text=Elory+SQL', 'Synthetic',
    100, 120, 40, 'ELORY-SQL-' || v_suffix, 10, 0, false, true, now(),
    '[]'::jsonb, '[]'::jsonb, NULL, 'ELORY-SQL-' || v_suffix, 0.1,
    '[]'::jsonb, '[]'::jsonb
  )
  RETURNING id INTO v_product_id;

  v_payload := jsonb_build_object(
    'idempotency_key', v_key,
    'user_id', NULL,
    'customer_access_token', 'local-test-' || v_suffix,
    'customer_name', 'Elory Local Test',
    'phone', '01000000000',
    'governorate', v_governorate,
    'center', v_center,
    'address', 'LOCAL TEST ONLY',
    'notes', 'ELORY_LOAD_TEST: transactional SQL test',
    'items', jsonb_build_array(jsonb_build_object(
      'product_id', v_product_id::text,
      'name', 'Synthetic fixture',
      'price', 1,
      'quantity', 2,
      'image', 'https://placehold.co/320x320/webp?text=Elory+SQL',
      'color', NULL,
      'size', NULL
    )),
    'payment_method', 'cash_on_delivery',
    'status', 'طلب جديد',
    'prime', false,
    'prime_requested', false,
    'coupon_code', NULL,
    'coupon_discount', 0,
    'coupon_free_shipping', false,
    'prime_discount', 0,
    'prime_free_shipping', false,
    'subtotal', 2,
    'shipping_cost', 0,
    'total', 2,
    'profit', 0
  );

  v_result := public.elory_create_order_once(v_payload, v_key);
  v_order_id := (v_result->'order'->>'id')::uuid;
  IF v_order_id IS NULL OR (v_result->'order'->>'inventory_reserved')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'COD order was not created with an inventory reservation.';
  END IF;

  v_result := public.elory_create_order_once(v_payload, v_key);
  v_replay_id := (v_result->'order'->>'id')::uuid;
  IF v_replay_id IS DISTINCT FROM v_order_id OR (v_result->>'replayed')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'COD idempotency replay created a second order.';
  END IF;

  SELECT stock INTO v_stock FROM public.products WHERE id = v_product_id;
  SELECT count(*) INTO v_reservations
    FROM private.elory_order_inventory_reservations
   WHERE order_id = v_order_id AND restored_at IS NULL;
  IF v_stock <> 8 OR v_reservations <> 1 THEN
    RAISE EXCEPTION 'COD replay reserved stock more than once (stock %, reservations %).', v_stock, v_reservations;
  END IF;

  UPDATE public.orders SET status = 'ملغي' WHERE id = v_order_id;
  SELECT stock INTO v_stock FROM public.products WHERE id = v_product_id;
  IF v_stock <> 10 THEN
    RAISE EXCEPTION 'COD cancellation did not restore the exact stock (got %).', v_stock;
  END IF;

  v_key := gen_random_uuid();
  v_payload := jsonb_set(v_payload, '{idempotency_key}', to_jsonb(v_key::text), true);
  v_payload := jsonb_set(v_payload, '{payment_method}', to_jsonb('card'::text), true);
  v_payload := jsonb_set(v_payload, '{items,0,quantity}', to_jsonb(1), true);

  v_result := public.elory_create_order_once(v_payload, v_key);
  v_order_id := (v_result->'order'->>'id')::uuid;
  IF v_order_id IS NULL OR (v_result->'order'->>'inventory_reserved')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'Paymob pending order did not reserve inventory.';
  END IF;

  v_session := public.elory_claim_order_payment_session(v_key, v_order_id, 'card');
  IF v_session->>'status' <> 'claimed' THEN
    RAISE EXCEPTION 'First Paymob payment-session claim should be claimed, got %.', v_session;
  END IF;

  IF public.elory_complete_order_payment_session(v_key, 'local-test-client-secret', 'local-test-intention') IS NOT TRUE THEN
    RAISE EXCEPTION 'Paymob test session could not be marked ready.';
  END IF;

  v_session := public.elory_claim_order_payment_session(v_key, v_order_id, 'card');
  IF v_session->>'status' <> 'ready' OR v_session->>'client_secret' <> 'local-test-client-secret' THEN
    RAISE EXCEPTION 'Paymob replay did not return the original ready session.';
  END IF;

  UPDATE public.orders SET status = 'فشل الدفع' WHERE id = v_order_id;
  SELECT stock INTO v_stock FROM public.products WHERE id = v_product_id;
  IF v_stock <> 10 THEN
    RAISE EXCEPTION 'Paymob failure did not restore the reserved stock (got %).', v_stock;
  END IF;

  RAISE NOTICE 'PASS: COD idempotency, one-time reservation, COD cancellation restore, Paymob session replay and payment-failure restore.';
END;
$$;

ROLLBACK;
