-- Transactional integration tests. Run only against a disposable PostgreSQL database
-- after order_inventory_fixture.sql and the migration have been applied.
BEGIN;

DO $test$
DECLARE
  v_stock integer;
  v_failed boolean;
  v_error text;
  v_items jsonb;
BEGIN
  INSERT INTO public.products(id, stock, name)
  VALUES
    ('00000000-0000-0000-0000-000000000001', 10, 'Fixture A'),
    ('00000000-0000-0000-0000-000000000002', 1, 'Fixture B'),
    ('00000000-0000-0000-0000-000000000003', 5, 'Fixture C');

  -- COD awaiting confirmation and online payment pending/failed do not reserve stock.
  INSERT INTO public.orders(id, status, payment_method, items, customer_access_token)
  VALUES
    ('10000000-0000-0000-0000-000000000001', 'جاري التأكيد', 'cash_on_delivery',
     '[{"product_id":"00000000-0000-0000-0000-000000000001","quantity":2}]'::jsonb, repeat('a',32)),
    ('10000000-0000-0000-0000-000000000002', 'جاري الدفع', 'card',
     '[{"product_id":"00000000-0000-0000-0000-000000000001","quantity":3}]'::jsonb, repeat('b',32)),
    ('10000000-0000-0000-0000-000000000003', 'فشل الدفع', 'vodafone_cash',
     '[{"product_id":"00000000-0000-0000-0000-000000000001","quantity":4}]'::jsonb, repeat('c',32));

  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 10 THEN RAISE EXCEPTION 'Pending/failed orders changed stock'; END IF;

  -- First confirmation deducts once; moving through confirmed fulfillment states does not deduct again.
  UPDATE public.orders SET status='طلب جديد'
   WHERE id='10000000-0000-0000-0000-000000000001';
  UPDATE public.orders SET status='جاري التجهيز'
   WHERE id='10000000-0000-0000-0000-000000000001';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 8 THEN RAISE EXCEPTION 'Confirmation must deduct exactly once'; END IF;

  -- Cancellation restores from the state ledger even after an intermediate status regression.
  UPDATE public.orders SET status='جديد'
   WHERE id='10000000-0000-0000-0000-000000000001';
  UPDATE public.orders SET status='ملغي'
   WHERE id='10000000-0000-0000-0000-000000000001';
  UPDATE public.orders SET status='ملغي'
   WHERE id='10000000-0000-0000-0000-000000000001';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 10 THEN RAISE EXCEPTION 'Cancellation must restore exactly once'; END IF;

  UPDATE public.orders SET status='تم التأكيد'
   WHERE id='10000000-0000-0000-0000-000000000001';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 8 THEN RAISE EXCEPTION 'Re-confirmation after cancellation must deduct again'; END IF;

  -- Deleting an active confirmed order must restore its stock before the state row cascades away.
  DELETE FROM public.orders WHERE id='10000000-0000-0000-0000-000000000001';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 10 THEN RAISE EXCEPTION 'Deleting an active order must restore deducted stock'; END IF;

  -- Duplicate lines for one product are aggregated before deduction/restoration.
  INSERT INTO public.orders(id, status, payment_method, items)
  VALUES ('10000000-0000-0000-0000-000000000004', 'جاري التأكيد', 'cash_on_delivery',
    '[{"product_id":"00000000-0000-0000-0000-000000000001","quantity":2},{"product_id":"00000000-0000-0000-0000-000000000001","quantity":3}]'::jsonb);
  UPDATE public.orders SET status='تم التأكيد'
   WHERE id='10000000-0000-0000-0000-000000000004';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 5 THEN RAISE EXCEPTION 'Duplicate product lines were not aggregated'; END IF;
  UPDATE public.orders SET status='ملغي'
   WHERE id='10000000-0000-0000-0000-000000000004';
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 10 THEN RAISE EXCEPTION 'Aggregated order stock was not restored'; END IF;

  -- Insufficient stock rejects confirmation and rolls back the status transition.
  INSERT INTO public.orders(id, status, payment_method, items)
  VALUES ('10000000-0000-0000-0000-000000000005', 'جاري التأكيد', 'cash_on_delivery',
    '[{"product_id":"00000000-0000-0000-0000-000000000002","quantity":2}]'::jsonb);
  v_failed := false;
  BEGIN
    UPDATE public.orders SET status='تم التأكيد'
     WHERE id='10000000-0000-0000-0000-000000000005';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
    v_failed := position('المخزون غير كافٍ' in v_error) > 0;
  END;
  IF NOT v_failed THEN RAISE EXCEPTION 'Insufficient stock did not reject confirmation'; END IF;
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000002';
  IF v_stock <> 1 THEN RAISE EXCEPTION 'Insufficient stock attempt changed product stock'; END IF;
  IF (SELECT status FROM public.orders WHERE id='10000000-0000-0000-0000-000000000005') <> 'جاري التأكيد' THEN
    RAISE EXCEPTION 'Failed confirmation did not roll back order status';
  END IF;

  -- A multi-product failure must roll back earlier product updates in the same trigger.
  INSERT INTO public.orders(id, status, payment_method, items)
  VALUES ('10000000-0000-0000-0000-000000000006', 'جاري التأكيد', 'cash_on_delivery',
    '[{"product_id":"00000000-0000-0000-0000-000000000001","quantity":2},{"product_id":"00000000-0000-0000-0000-000000000002","quantity":2}]'::jsonb);
  v_failed := false;
  BEGIN
    UPDATE public.orders SET status='تم التأكيد'
     WHERE id='10000000-0000-0000-0000-000000000006';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
    v_failed := position('المخزون غير كافٍ' in v_error) > 0;
  END;
  IF NOT v_failed THEN RAISE EXCEPTION 'Multi-product insufficient stock did not reject confirmation'; END IF;
  SELECT stock INTO v_stock FROM public.products WHERE id='00000000-0000-0000-0000-000000000001';
  IF v_stock <> 10 THEN RAISE EXCEPTION 'Multi-product failure partially deducted stock'; END IF;

  -- Product changes and deletion are blocked while a confirmed order holds stock.
  INSERT INTO public.orders(id, status, payment_method, items)
  VALUES ('10000000-0000-0000-0000-000000000007', 'جاري التأكيد', 'cash_on_delivery',
    '[{"product_id":"00000000-0000-0000-0000-000000000003","quantity":1}]'::jsonb);
  UPDATE public.orders SET status='تم التأكيد'
   WHERE id='10000000-0000-0000-0000-000000000007';
  v_failed := false;
  BEGIN
    UPDATE public.orders
       SET items='[{"product_id":"00000000-0000-0000-0000-000000000003","quantity":2}]'::jsonb
     WHERE id='10000000-0000-0000-0000-000000000007';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
    v_failed := position('لا يمكن تعديل منتجات طلب' in v_error) > 0;
  END;
  IF NOT v_failed THEN RAISE EXCEPTION 'Changing active order items was not blocked'; END IF;

  v_failed := false;
  BEGIN
    DELETE FROM public.products WHERE id='00000000-0000-0000-0000-000000000003';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_error = MESSAGE_TEXT;
    v_failed := position('لا يمكن حذف منتج مرتبط' in v_error) > 0;
  END;
  IF NOT v_failed THEN RAISE EXCEPTION 'Deleting a product in an active order was not blocked'; END IF;

  UPDATE public.orders SET status='ملغي'
   WHERE id='10000000-0000-0000-0000-000000000007';
  DELETE FROM public.products WHERE id='00000000-0000-0000-0000-000000000003';

  -- Customer RPCs retain visible fields and remove internal inventory/cost identifiers.
  INSERT INTO public.orders(id, status, payment_method, items, customer_access_token)
  VALUES ('10000000-0000-0000-0000-000000000008', 'طلب جديد', 'cash_on_delivery',
    '[{"product_id":"00000000-0000-0000-0000-000000000001","name":"Visible item","price":25,"quantity":1,"code":"secret-code","sku":"secret-sku","stock":88,"product_code":"secret-product-code","wholesale_price":7,"cost_price":6}]'::jsonb,
    repeat('z',32));

  SELECT items INTO v_items
    FROM public.get_customer_orders(repeat('z',32), NULL)
   WHERE id='10000000-0000-0000-0000-000000000008';
  IF v_items IS NULL OR jsonb_array_length(v_items) <> 1 THEN
    RAISE EXCEPTION 'Legacy customer order RPC did not return the authorized order';
  END IF;
  IF (v_items->0) ?| ARRAY['code','sku','stock','product_code','wholesale_price','cost_price']
     OR v_items->0->>'name' IS DISTINCT FROM 'Visible item'
     OR v_items->0->>'price' IS DISTINCT FROM '25' THEN
    RAISE EXCEPTION 'Legacy customer RPC redaction contract failed';
  END IF;

  SELECT items INTO v_items
    FROM public.get_customer_orders_v2(repeat('z',32), NULL)
   WHERE id='10000000-0000-0000-0000-000000000008';
  IF v_items IS NULL OR (v_items->0) ?| ARRAY['code','sku','stock','product_code','wholesale_price','cost_price'] THEN
    RAISE EXCEPTION 'Customer order v2 RPC redaction contract failed';
  END IF;

  RAISE NOTICE 'Elory inventory lifecycle and customer privacy integration tests passed.';
END;
$test$;

ROLLBACK;
