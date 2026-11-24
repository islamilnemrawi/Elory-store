# Elory release-readiness handoff

Snapshot: 24 November 2026  
Repository: `islamilnemrawi/Elory-store`  
Production source branch: `main`

## Changes prepared in this branch

- Removed unsafe inline JavaScript interpolation from dynamic shop-category buttons. Category values now travel through escaped data attributes and a delegated click handler.
- Removed unsafe inline JavaScript interpolation from customer-order product buttons. Product IDs now travel through escaped data attributes and a delegated click handler.
- Added a Playwright regression test that injects hostile category names and order product IDs and verifies that no inline handler is created or executed.
- Synchronized the repository copy of `admin-reset-staff-password` with the currently deployed Edge Function. The primary-owner identity remains the security boundary; the editable `role` label is not treated as proof of primary-owner identity.
- Added a direct WhatsApp request path to the data-deletion page using the same published store contact already present on the storefront.
- Preserved both source modules returned by the deployed `elora-push` Worker under `cloudflare/push-worker/`. This is a source snapshot, not a Worker redeployment package; confirm the active entrypoint and bindings before any future upload.

## Production gates still open

### Supabase database

The live migration history and root SQL files are not reconciled. See [Supabase migration reconciliation](supabase-migration-reconciliation.md). Do not push or repair migration history until all source SQL is recovered and matched.

The Security Advisor still reports:
- Leaked-password protection disabled.
- `pg_net` installed in the `public` schema.
- Five anon-callable `SECURITY DEFINER` RPCs and authenticated-callable privileged RPCs. These must be reviewed one-by-one against their intended caller flows; do not revoke grants in bulk.
- RLS-enabled tables without policies, including private/server-only tables and administrative audit/settings tables. Do not add generic policies simply to silence the advisor.

Performance Advisor reports unused indexes and a multiple-permissive-policy warning. Do not drop indexes without query-plan and workload evidence.

### Payments

The deployed Paymob function defaults to `PAYMOB_MODE=test` when the setting is absent. Secret values and the live/test mode were not inspected. Before accepting real payments, confirm in Supabase Function Secrets that `PAYMOB_MODE=live` and the correct live API, secret, HMAC, public-key, and integration values are configured. Then run a controlled end-to-end payment test with the payment provider. No real charge was made during this work.

### Account security

- Cloudflare account-level 2FA enforcement is currently disabled. Enroll the account owner and all required administrators in 2FA first; only then consider enforcement to avoid locking out the account.
- Supabase leaked-password protection must be enabled in the Supabase Auth security settings. This setting was not changed by this branch.
- Never put service-role keys, Firebase service-account JSON, Paymob secrets, or private signing keys in the repository.

### Hosting

GitHub Pages is the currently verified canonical storefront. Cloudflare Pages has production deployments disabled, so pushes to `main` are skipped there. Its `pages.dev` copy is not a verified mirror of the current main commit. Keep GitHub Pages canonical unless a separate, tested decision is made to re-enable Cloudflare Pages production deployments.

### Android dashboard

The current verified artifact is a **Debug APK**, not a signed production Release APK. Android unit tests and Debug APK build/verification passed on workflow run [45391917325](https://github.com/islamilnemrawi/Elory-store/actions/runs/45391917325).

Google Play release still requires a production signing keystore, versionCode/versionName review, targetSdk compatibility review, a signed Release build, device testing of the exact Release APK, and Play Console privacy/data-safety declarations. Do not treat the Debug APK as Play Store-ready.

## Verification expected from this branch

- PostgreSQL inventory/privacy integration tests run against an isolated disposable PostgreSQL service in GitHub Actions.
- Playwright storefront audit plus the new stored-XSS regression test run in GitHub Actions.
- The Worker source snapshot is syntax-checked without deploying it.
- No Supabase schema/migration, Edge Function deployment, Cloudflare Pages deployment, payment transaction, or Android signing key is changed by this branch.

## Release decision

This branch is a safer, testable release candidate, but the whole business system must not be labelled fully production-ready until the database migration history, Paymob live configuration, account 2FA, Auth leaked-password protection, and signed Android release requirements are resolved and verified.
