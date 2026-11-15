-- Enforce the dashboard's global store-open switch at the database boundary.
-- Missing legacy settings are treated as OPEN to preserve existing production behavior.

CREATE OR REPLACE FUNCTION private.enforce_store_open_on_new_orders()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.site_customizations sc
    WHERE sc.id = 1
      AND sc.config #>> '{global,isStoreOpen}' = 'false'
  ) THEN
    RAISE EXCEPTION 'المتجر مغلق مؤقتًا ولا يستقبل طلبات جديدة';
  END IF;

  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.enforce_store_open_on_new_orders()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_elory_store_availability_guard ON public.orders;
CREATE TRIGGER trg_elory_store_availability_guard
BEFORE INSERT ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.enforce_store_open_on_new_orders();

NOTIFY pgrst, 'reload schema';
