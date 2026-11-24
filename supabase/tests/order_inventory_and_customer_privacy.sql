-- Read-only contract checks for 20261124130000_elory_order_inventory_and_customer_privacy.sql.
-- Run after applying the migration to a disposable database or approved staging project.

DO $test$
DECLARE
  v_definition text;
  v_item jsonb;
  v_rls boolean;
BEGIN
  IF to_regclass('private.elory_order_inventory_state') IS NULL THEN
    RAISE EXCEPTION 'Missing private inventory idempotency state table';
  END IF;

  SELECT c.relrowsecurity
    INTO v_rls
    FROM pg_class c
   WHERE c.oid = 'private.elory_order_inventory_state'::regclass;
  IF v_rls IS DISTINCT FROM true THEN
    RAISE EXCEPTION 'Inventory state table must have RLS enabled';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
     WHERE tgrelid = 'public.orders'::regclass
       AND tgname = 'elory_sync_order_inventory_status'
       AND NOT tgisinternal
  ) THEN
    RAISE EXCEPTION 'Missing order status inventory trigger';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger
     WHERE tgrelid = 'public.orders'::regclass
       AND tgname = 'elory_sync_order_inventory_insert'
       AND NOT tgisinternal
  ) THEN
    RAISE EXCEPTION 'Missing order insert inventory trigger';
  END IF;

  SELECT pg_get_functiondef('private.elory_sync_order_inventory()'::regprocedure)
    INTO v_definition;
  IF position('FOR UPDATE' IN v_definition) = 0
     OR position('stock = p.stock - v_item.quantity' IN v_definition) = 0
     OR position('stock = p.stock + v_item.quantity' IN v_definition) = 0
     OR position('restored_at = NULL' IN v_definition) = 0 THEN
    RAISE EXCEPTION 'Inventory trigger must lock its state and support idempotent deduction/restoration';
  END IF;

  SELECT pg_get_functiondef('public.get_customer_orders_v2(text,text)'::regprocedure)
    INTO v_definition;
  IF position('- ''code''' IN v_definition) = 0
     OR position('- ''sku''' IN v_definition) = 0
     OR position('- ''stock''' IN v_definition) = 0 THEN
    RAISE EXCEPTION 'Customer order v2 RPC is missing internal item-field redaction';
  END IF;

  SELECT pg_get_functiondef('public.get_customer_orders(text,text)'::regprocedure)
    INTO v_definition;
  IF position('- ''code''' IN v_definition) = 0
     OR position('- ''sku''' IN v_definition) = 0
     OR position('- ''stock''' IN v_definition) = 0 THEN
    RAISE EXCEPTION 'Legacy customer order RPC is missing internal item-field redaction';
  END IF;

  v_item := jsonb_build_object(
    'code', 'internal-code',
    'sku', 'internal-sku',
    'stock', 99,
    'name', 'Customer-visible name',
    'price', 100,
    'quantity', 1
  ) - 'code' - 'sku' - 'stock';

  IF v_item ?| ARRAY['code', 'sku', 'stock']
     OR v_item->>'name' IS DISTINCT FROM 'Customer-visible name'
     OR v_item->>'price' IS DISTINCT FROM '100' THEN
    RAISE EXCEPTION 'Customer item redaction removed visible fields or retained private fields';
  END IF;
END;
$test$;
