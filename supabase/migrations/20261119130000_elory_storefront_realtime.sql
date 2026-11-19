-- Enable narrowly scoped Supabase Realtime events for storefront data that the
-- public website already reads. Existing RLS policies remain unchanged.
DO $$
DECLARE
  target_table text;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime'
  ) THEN
    RAISE EXCEPTION 'Supabase publication supabase_realtime does not exist';
  END IF;

  FOREACH target_table IN ARRAY ARRAY[
    'products',
    'categories',
    'shipping_governorates',
    'shipping_centers',
    'prime_subscriptions'
  ]
  LOOP
    IF NOT EXISTS (
      SELECT 1
      FROM pg_publication_tables
      WHERE pubname = 'supabase_realtime'
        AND schemaname = 'public'
        AND tablename = target_table
    ) THEN
      EXECUTE format('ALTER PUBLICATION supabase_realtime ADD TABLE public.%I', target_table);
    END IF;
  END LOOP;
END
$$;
