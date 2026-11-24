# Archived migration source candidates

These SQL files were recovered read-only from the legacy `islamilnemrawi/pinky--dashboard` repository on 24 November 2026.

They are preserved here as historical source evidence for Supabase migration reconciliation. **They are not active migrations and must not be copied or applied automatically.**

Mapping notes:
- `20261108124700_elory_site_cms_storage_access.sql` matches a live migration version and name exactly.
- `20261116122727_elory_cms_draft_publish.sql` matches one live version/name; the live history also contains another entry with the same name at a different version.
- `20261114070500_create_elory_hero_ads_bucket.sql` and `20261118120000_owner_prime_subscription_delete.sql` match live migration names but have timestamp differences.
- `20261111061000_elory_operations_hardening.sql`, `20261115130500_repair_coupon_staff_rls.sql`, and `20261116030000_profit_dashboard_rpc.sql` are possible historical candidates for related live operations; their exact mapping must be proven by SQL-content and schema comparison.

The active Supabase migration directory remains `supabase/migrations/`. Keep this archive separate until every migration has been mapped and reviewed.
