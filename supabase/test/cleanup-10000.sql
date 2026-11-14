BEGIN;

-- Deleting synthetic orders fires the inventory-restore trigger first.
DELETE FROM public.orders
 WHERE notes LIKE 'ELORY_LOAD_TEST:%';

DELETE FROM public.products
 WHERE sku LIKE 'ELORY-LOAD-%';

DELETE FROM storage.objects
 WHERE bucket_id = 'elory-load-test';
DELETE FROM storage.buckets
 WHERE id = 'elory-load-test';

DELETE FROM public.shipping_centers
 WHERE governorate = 'ELORY LOAD TEST';
DELETE FROM public.shipping_governorates
 WHERE governorate = 'ELORY LOAD TEST';

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
    FROM public.products
   WHERE sku LIKE 'ELORY-LOAD-%';
  IF v_count <> 0 THEN
    RAISE EXCEPTION 'Synthetic product cleanup incomplete: % rows remain.', v_count;
  END IF;
END;
$$;

COMMIT;
