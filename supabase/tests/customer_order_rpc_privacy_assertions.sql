SET ROLE anon;
DO $anon_order_history$
DECLARE
  v_count integer;
  v_item jsonb;
BEGIN
  PERFORM set_config('request.jwt.claim.sub', '', true);

  IF has_table_privilege('anon','public.orders','SELECT') THEN
    RAISE EXCEPTION 'Anonymous users unexpectedly have direct orders table access';
  END IF;

  SELECT count(*) INTO v_count
    FROM public.get_customer_orders_v2('guest-token-12345678901234567890', NULL);
  IF v_count <> 2 THEN
    RAISE EXCEPTION 'Customer order v2 must hide failed and unconfirmed online orders; expected 2, got %', v_count;
  END IF;

  SELECT count(*) INTO v_count
    FROM public.get_customer_orders('guest-token-12345678901234567890', NULL);
  IF v_count <> 2 THEN
    RAISE EXCEPTION 'Legacy customer order RPC visibility changed; expected 2, got %', v_count;
  END IF;

  SELECT count(*) INTO v_count
    FROM public.get_customer_orders_v2('wrong-token-12345678901234567890', NULL);
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'A wrong customer access token returned orders';
  END IF;

  SELECT items->0 INTO v_item
    FROM public.get_customer_orders_v2('guest-token-12345678901234567890', NULL)
   WHERE order_number = 'ORD-COD';

  IF v_item->>'code' IS DISTINCT FROM 'ELORY-CODE-1' THEN
    RAISE EXCEPTION 'Customer-facing order item code must remain available';
  END IF;
  IF v_item->>'name' IS DISTINCT FROM 'Test product'
     OR v_item->>'image' IS DISTINCT FROM 'https://example.test/public.webp'
     OR v_item->>'price' IS DISTINCT FROM '100'
     OR v_item->>'quantity' IS DISTINCT FROM '1' THEN
    RAISE EXCEPTION 'Customer-facing order item fields were lost';
  END IF;
  IF v_item ?| ARRAY[
    'wholesale_price','product_code','product_image','product_name',
    'wholesalePrice','productCode','productImage','productName',
    'sku','product_sku','productSku','internal_code','internalCode',
    'barcode','cost_price','costPrice','unit_cost','unitCost',
    'product_cost','profit','margin'
  ] THEN
    RAISE EXCEPTION 'Customer order RPC leaked internal item fields: %', v_item;
  END IF;
END;
$anon_order_history$;
RESET ROLE;

SET ROLE authenticated;
DO $authenticated_order_history$
DECLARE
  v_count integer;
BEGIN
  PERFORM set_config('request.jwt.claim.sub', 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', true);

  SELECT count(*) INTO v_count
    FROM public.get_customer_orders_v2(NULL, NULL);

  IF v_count <> 1 THEN
    RAISE EXCEPTION 'Authenticated customer must only receive their own order; expected 1, got %', v_count;
  END IF;
END;
$authenticated_order_history$;
RESET ROLE;
