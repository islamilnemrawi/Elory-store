# Elory Supabase security hardening

## Scope

This change is isolated on branch `elory/security-hardening`. It does not edit the live store HTML, the dashboard bundle, production database rows, secrets, or Edge Function deployments.

The single migration `20261114180000_elory_security_privilege_hardening.sql` is designed to preserve the existing PostgREST RPC names, input signatures, return types, defaults, volatility, and direct role grants.

## Database changes

1. The 22 existing API-facing `SECURITY DEFINER` implementations are moved, without changing their function OIDs or bodies, into the non-exposed `private` schema. Public RPC names are recreated as `SECURITY INVOKER` wrappers that call those original implementations. Existing RLS policy dependencies that reference `has_staff_permission` retain the same function OID; authenticated receives the required private-schema usage and exact execute grants.
2. Before moving a function, the migration checks that it exists exactly once, has no PUBLIC execute grant, and contains the expected staff, user-identity, or guest access-token gate. The migration stops rather than proceeding if these safeguards are not present.
3. `public.validate_coupon(text,numeric)` becomes `SECURITY INVOKER`. Its active-only coupon SELECT policy is checked before the change, so RLS applies to anonymous and ordinary authenticated buyers. The staff coupon SELECT policy is changed from RESTRICTIVE to PERMISSIVE: signed-in customers retain access to active coupons, while staff with `coupons.view` can additionally see inactive coupons in the dashboard.
4. `TRUNCATE`, `REFERENCES`, `TRIGGER`, and (on PostgreSQL 17+) `MAINTAIN` are revoked from `anon` and `authenticated` on public objects. Existing SELECT/INSERT/UPDATE/DELETE grants and RLS policies are not rewritten.
5. API roles receive `USAGE`, but not `CREATE`, on `private` so wrappers and policy helpers can resolve the approved implementations. New private tables/functions created by `postgres` default to no API-role access.
6. PostgreSQL defaults for objects created by `postgres` are tightened, including the global default PUBLIC function EXECUTE grant.
7. `private.elora_push_config` remains RLS-protected and inaccessible to API roles. It deliberately has no client-facing policy.

## Intentionally preserved access

- `get_customer_orders` remains available to `anon` and `authenticated` for guest order tracking. Its implementation accepts the authenticated owner or a high-entropy customer access token (minimum 24 characters).
- `redeem_coupon` remains available to `anon`, `authenticated`, and `service_role` for the existing guest checkout and payment flow. Its original order-ownership/access-token checks are retained. The Paymob callback uses the `service_role` key without a customer access token, so the regression suite exercises that exact server-side path.
- Admin RPCs retain their authenticated role grants because the dashboard calls them. Their existing `has_staff_permission(...)` checks are retained in the private implementation; anonymous execution is not granted.
- Staff helpers retain authenticated execution because existing RLS policies and dashboard code depend on them.

The internal implementations remain SECURITY DEFINER by design. They are no longer exposed as functions in PostgREST's public schema. The `private` schema must not be added to the project's Data API Exposed Schemas. The migration can detect explicit database-level or `authenticator` role overrides in `pg_db_role_setting`, but it cannot reliably read the Dashboard-managed Data API schema list; verify that list separately before applying the migration.

## Explicitly not changed

- `pg_net` is currently installed in `public` and PostgreSQL reports the extension as non-relocatable. This migration does not drop/recreate it or attempt an unsupported move; doing so without reviewing its dependent functions/jobs could interrupt database notifications or integrations. The corresponding Advisor notice may remain until a separately planned extension reinstall is verified.
- Supabase Auth leaked-password protection is a dashboard/plan capability, not a SQL setting. Supabase documents availability on Pro and above. No plan upgrade or charge is authorized here, so it is not enabled by this migration.
- The INFO notice for `private.elora_push_config` having RLS but no policies is intentional: it is a private configuration table with no client access.
- Provider-managed defaults belonging to `supabase_admin` cannot be altered directly by project SQL. The migration updates `postgres` defaults and current public objects; new objects created by provider-managed roles still need explicit review.

## Verification

The GitHub Actions workflow `.github/workflows/security-hardening.yml` starts a disposable PostgreSQL 17 service and runs:

1. A synthetic schema/privilege fixture matching the audited RPC signatures and grants.
2. The migration itself.
3. Regression assertions for wrapper/security-definer placement, grant preservation, private helper access through RLS policies, anonymous guest-order restrictions, coupon RLS behavior, current-table privilege removal, and tightened defaults for future objects.

A separate `.github/workflows/dashboard-security-compatibility.yml` workflow extracts the canonical dashboard ZIP from `pinky--dashboard`, runs its existing CMS/operations/order-item patch and verification scripts on that clean source archive, and builds the Android debug APK. This verifies that the current dashboard build and its patched source remain compilable without modifying the dashboard repository.

These isolated CI checks do not use production records or credentials and are not a live Supabase branch test. The Elory-store repository currently contains this new security migration but not the historical schema migrations already recorded in the production project, so a clean Supabase local stack cannot reconstruct the complete live schema from this repository alone. Exporting a schema-only baseline (without customer rows or secrets) or providing a no-cost isolated Supabase environment is required for full end-to-end testing. Before applying the migration to production, the project must be backed up and the actual admin dashboard, guest-order tracking, coupon validation/redemption as both guest and signed-in customer, staff access to inactive coupons, Paymob callback redemption, Prime, push registration, and Auth flows must be verified against that isolated environment. Do not merge or apply the migration solely because synthetic CI checks pass.
