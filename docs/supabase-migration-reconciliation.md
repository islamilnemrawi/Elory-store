# Supabase migration reconciliation — 24 November 2026

## Current inventory (read-only comparison)

- Live Supabase migration history: **59** entries.
- Root repository SQL migrations: **25** files.
- Matching migration names: **22**.
- Matching names whose local filename timestamp differs from the live version: **16**.
- Live history entries with no same-named root SQL source file: **37**.
- Root SQL files whose names do not appear in live history: **3**.

These are source/history reconciliation discrepancies, not proof that the live database is broken. Several local files have the same migration name as a live entry but a different timestamp, so comparing timestamps alone is misleading.

## Live entries without a same-named root SQL source

- `20261108124700` — `elory_site_cms_storage_access`
- `20261108133546` — `elory_shipping_owner_policy_hardening`
- `20261108134410` — `elory_staff_permission_aliases_and_rpc_hardening`
- `20261108135014` — `elory_order_item_cost_snapshots`
- `20261108142823` — `harden_coupon_permissions_and_order_snapshots`
- `20261108142932` — `fix_shipping_center_permissions_and_coupon_redemption`
- `20261108143205` — `repair_prime_checkout_activation`
- `20261108143229` — `fix_order_identity_random_token_schema`
- `20261108143359` — `validate_order_prices_shipping_and_coupons_server_side`
- `20261108143500` — `close_prime_subscription_policy_bypass_and_clean_rls`
- `20261108143809` — `mark_prime_pending_failed_when_paymob_intention_fails`
- `20261108143916` — `bind_customer_order_user_to_auth_identity`
- `20261108144033` — `support_product_variant_pricing_in_order_validation`
- `20261108144123` — `enforce_valid_order_contact_and_shipping_destination`
- `20261108144529` — `correct_prime_free_shipping_usage_and_pending_status`
- `20261108144656` — `consolidate_permissive_rls_policies_without_access_regression`
- `20261111060805` — `elory_shipping_rpc_and_prime_trigger_cleanup`
- `20261111061432` — `elory_prime_subscription_admin_and_lifecycle_consistency`
- `20261111061516` — `elory_coupon_redemption_ownership_validation`
- `20261114070042` — `create_elory_hero_ads_bucket`
- `20261115131853` — `repair_coupon_rls_staff_permissions`
- `20261115185805` — `grant_staff_profiles_service_role_access`
- `20261115203926` — `correct_order_profit_after_coupon_and_unknown_costs`
- `20261115212556` — `finance_analytics_profit_integrity_and_prime_cost_tracking`
- `20261116094512` — `elory_prime_dynamic_config_and_profit`
- `20261116095116` — `elory_prime_packaging_on_orders`
- `20261116095832` — `elory_prime_payment_confirmation_and_reactivation`
- `20261116100108` — `elory_prime_preserve_order_purchase_price`
- `20261116102654` — `courier_shipping_cost_snapshots_and_profit`
- `20261116102839` — `restrict_legacy_prime_shipping_cost_rpc`
- `20261116103219` — `refresh_courier_cost_when_order_destination_changes`
- `20261116103330` — `remove_duplicate_prime_shipping_cost_json_fields`
- `20261116122727` — `elory_cms_draft_publish`
- `20261116123515` — `elory_cms_draft_publish`
- `20261116194247` — `elory_cms_versions_and_rollback_20261116193000`
- `20261118115939` — `owner_prime_subscription_delete`
- `20261121223749` — `elory_category_product_name_sync`

## Local root files not represented by a same-named live history entry

- `20261116193000_elory_cms_versions_and_rollback.sql`
- `20261118140000_customer_failed_payment_visibility.sql`
- `20261119130000_elory_storefront_realtime.sql`

## Same-name timestamp mismatches

| Local file | Live version |
|---|---|
| `20261115131000_elory_secure_coupon_redemptions.sql` | `20261115114259` |
| `20261115134500_elory_coupon_redemption_total_fix.sql` | `20261115114605` |
| `20261115142000_elory_store_availability_guard.sql` | `20261115121233` |
| `20261117084800_secure_paymob_order_visibility_and_push.sql` | `20261117065831` |
| `20261117084900_exclude_unpaid_orders_from_customer_metrics.sql` | `20261117065851` |
| `20261117085000_allow_paid_order_fulfillment_updates.sql` | `20261117070500` |
| `20261117085100_backfill_product_color_swatches.sql` | `20261117070755` |
| `20261117085200_hide_unconfirmed_online_customer_rows.sql` | `20261117070949` |
| `20261117085300_defer_coupon_redemption_until_payment_confirmation.sql` | `20261117072906` |
| `20261117085400_block_manual_promotion_of_legacy_online_orders.sql` | `20261117073406` |
| `20261117085500_hide_unconfirmed_online_orders_with_rls.sql` | `20261117073510` |
| `20261117093000_elory_cms_restore_atomic_draft_clear.sql` | `20261116225756` |
| `20261118121000_elory_product_delete_and_order_workflow.sql` | `20261118102654` |
| `20261118130000_elory_order_status_and_delete_repair.sql` | `20261118122156` |
| `20261118131000_customer_order_payment_method.sql` | `20261118122514` |
| `20261124130000_elory_order_inventory_and_customer_privacy.sql` | `20261124112349` |

## Required safe reconciliation sequence

1. Keep the current production schema and data unchanged.
2. Obtain the original SQL source for every missing live migration from trusted repository history, backups, or the original author. Do not reconstruct SQL from migration names.
3. For each of the 16 timestamp mismatches, compare the complete SQL contents and verify the resulting live schema effects before deciding whether a filename/version repair is appropriate.
4. Determine whether the three unrecorded local files were applied manually, superseded, or never applied. Verify by schema/function/policy state and deployment history.
5. Keep Android dashboard migrations under `dashboard-android/`; do not copy them into root `supabase/migrations/` automatically.
6. Only after the full mapping is reviewed, prepare a dedicated migration-history reconciliation plan and a rollback/backup procedure.

**Do not run `supabase db push`, `supabase migration repair`, or apply any new migration until the reconciliation above is complete and independently reviewed.** No production migration or schema change was made as part of this audit.
