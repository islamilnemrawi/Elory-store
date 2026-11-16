-- Narrow privileges required by existing trusted Edge Function handlers.
-- Paymob reads the published Prime settings from site_customizations.
-- The push delivery worker updates stale/failed device rows.
-- No anon/authenticated privileges or RLS policies are changed.

GRANT SELECT ON TABLE public.site_customizations TO service_role;
GRANT UPDATE ON TABLE public.dashboard_push_devices TO service_role;
