# Elory release-readiness handoff

Snapshot: 24 November 2026  
Repository: `islamilnemrawi/Elory-store`  
Production source branch: `main`

## Changes prepared in this branch

- Removed unsafe inline JavaScript interpolation from dynamic shop-category pills, side-menu categories, homepage category links, product-card actions, favorites actions, cart quantity/removal actions, and customer-order product buttons. Product/category identifiers now travel through escaped data attributes and delegated click handlers while preserving existing action arguments and navigation behavior.
- Extended the Playwright stored-XSS regression suite with hostile category names, product IDs, and cart-item keys. It verifies that generated controls contain no inline handlers, delegated actions receive the original opaque identifiers, and injected strings are never executed.
- Added the largest layout-shift source details to the first-paint regression failure message, preserving the existing CLS threshold rather than weakening the test.
- Synchronized the repository copy of `admin-reset-staff-password` with the currently deployed Edge Function. The primary-owner identity remains the security boundary; the editable `role` label is not treated as proof of primary-owner identity.
- Added a direct WhatsApp request path to the data-deletion page using the same published store contact already present on the storefront.
- Preserved both source modules returned by the deployed `elora-push` Worker under `cloudflare/push-worker/`. This is a source snapshot, not a Worker redeployment package; confirm the active entrypoint and bindings before any future upload.
- Enabled Cloudflare Worker query-string redaction for `elora-push` observability and verified the setting by reading it back. Existing log sampling, persistence, and invocation-log settings were preserved.

## Production gates still open

### Supabase database

The live migration history and root SQL files are not reconciled: 59 live entries, 27 root SQL files, 8 exact version/name matches, 16 timestamp mismatches, 35 live entries without same-named root sources, and 3 local files absent by name from live history. Exact-path GitHub history searches did not recover the missing sources. See [Supabase migration reconciliation](supabase-migration-reconciliation.md). Do not push or repair migration history until all source SQL is recovered and matched.

The Security Advisor still reports:
- Leaked-password protection disabled.
- `pg_net` installed in the `public` schema.
- Five anon-callable `SECURITY DEFINER` RPCs and authenticated-callable privileged RPCs. A read-only review of `get_customer_orders`, `get_customer_orders_v2`, `redeem_coupon`, and both `validate_coupon` overloads confirmed that order retrieval and coupon redemption check the authenticated user identity or a 24-character access token; coupon validation is a deliberately public checkout lookup. These functions still need ongoing abuse/rate-limit review. Do not revoke grants in bulk.
- RLS-enabled tables without policies, including private/server-only tables and administrative audit/settings tables. A read-only ACL check confirmed that all five flagged tables deny both `anon` and `authenticated` SELECT/INSERT; the three public administrative tables grant table privileges only to `service_role`, while the two private tables have no client grants. These warnings are consistent with server-only access and should not be silenced by adding generic policies.

Performance Advisor reports unused indexes and a multiple-permissive-policy warning. Do not drop indexes without query-plan and workload evidence.

### Payments

The deployed Paymob function defaults to `PAYMOB_MODE=test` when the setting is absent. Secret values and the live/test mode were not inspected. Before accepting real payments, confirm in Supabase Function Secrets that `PAYMOB_MODE=live` and these live values are configured: `PAYMOB_LIVE_API_KEY`, `PAYMOB_LIVE_SECRET_KEY`, `PAYMOB_LIVE_HMAC`, `PAYMOB_LIVE_PUBLIC_KEY`, `PAYMOB_LIVE_INTEGRATION_ID`, and `PAYMOB_LIVE_WALLET_INTEGRATION_ID`. Keep the service-role secret configured separately. Never paste secret values into chat or commit them to GitHub. Then run a controlled end-to-end payment test with the payment provider. No real charge was made during this work.

### Account security

- Cloudflare account-level 2FA enforcement is currently disabled. Enroll the account owner and all required administrators in 2FA first; only then consider enforcement to avoid locking out the account.
- The Supabase organization is on the **Free** plan. Supabase documents leaked-password protection as Pro-and-above only, so this warning cannot be cleared without a paid upgrade. No upgrade is recommended for this project. As a free mitigation, review Authentication → Sign In / Providers → Email and set a strong minimum password length (at least 10–12 characters) plus required lowercase, uppercase, digits, and symbols; verify the current settings before changing them. This does not replace breached-password screening, and the Security Advisor warning may remain. See [Supabase password security](https://supabase.com/docs/guides/auth/password-security) and [plan comparison](https://supabase.com/pricing).
- Never put service-role keys, Firebase service-account JSON, Paymob secrets, or private signing keys in the repository.

### Hosting

GitHub Pages is the currently verified canonical storefront. Cloudflare Pages has production deployments disabled, so pushes to `main` are skipped there. Its `pages.dev` copy is not a verified mirror of the current main commit. Keep GitHub Pages canonical unless a separate, tested decision is made to re-enable Cloudflare Pages production deployments.

### Android dashboard

The current verified artifact is a **Debug APK**, not a signed production Release APK. Android unit tests and Debug APK build/verification passed on workflow run [45391917325](https://github.com/islamilnemrawi/Elory-store/actions/runs/45391917325).

Google Play release still requires a production signing keystore, versionCode/versionName review, targetSdk compatibility review, a signed Release build, device testing of the exact Release APK, and Play Console privacy/data-safety declarations. Do not treat the Debug APK as Play Store-ready.

## Performance verification

The earlier intermittent value of **0.4746** was produced by the test's previous implementation, which summed every layout-shift entry across the entire observation period. That is not the Core Web Vitals CLS calculation: CLS uses the largest session window, grouping shifts only while the gap is at most 1 second and the session duration is at most 5 seconds.

The regression test now calculates the maximum session-window value, retains per-entry source geometry, and separately records the raw sum for diagnostics. The pass threshold remains **0.1** and was not changed.

Latest verified run on the release-readiness branch (24 November 2026):
- Desktop 1365×900: CLS **0.00764** (below 0.1).
- Mobile 390×844: CLS **0.00000**.
- The largest desktop entry involved `#featured` moving 28.5px as the asynchronous product grid settled; its measured layout-shift score was approximately **0.00763**, not 0.4746.
- First-paint, reload-first-frame, category-rail motion, stored-XSS, desktop/mobile visual audit, and mobile notch/slow-scroll checks passed.

This corrects the test measurement rather than masking a page shift. No storefront CSS, content, CMS visibility, or production database values were changed for this correction.
 
## Browser audit result

- First-paint/reload stability, category-rail motion, stored-XSS regression, and mobile notch/slow-scroll checks passed on the isolated release-readiness branch (latest run set: [browser audit](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405743966), [mobile regression](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405743984), [JavaScript checks](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405744148), [PostgreSQL privacy/inventory tests](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405743939), [Worker syntax checks](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405743948)).

The Playwright audit on 24 November 2026 passed for the GitHub Pages production origin at mobile 390×844 and desktop 1365×900:
- HTTP 200 on both viewports.
- No horizontal overflow, broken product images, uncaught page errors, console errors, failed requests, or bad HTTP responses on the production origin.
- First-paint/reload stability, category-rail motion, and the stored-XSS regression test passed.
- The local branch preview at `http://127.0.0.1:4173` produced four console messages and two failed Paymob preflight requests because the deployed Paymob CORS allowlist intentionally permits the GitHub Pages origin, not localhost. Do not broaden production CORS just to silence this local-only test condition.
- The audit deliberately skips clicking live checkout/auth/order buttons to avoid creating or modifying production customer data. It is a visual/read-only browser audit, not a complete transactional E2E test.

The screenshots and JSON audit report are retained in the GitHub Actions artifact for the successful browser-audit run.

## Verification expected from this branch

- PostgreSQL inventory/privacy integration tests run against an isolated disposable PostgreSQL service in GitHub Actions.
- Playwright storefront audit plus the new stored-XSS regression test run in GitHub Actions.
- The Worker source snapshot is syntax-checked without deploying it.
- No Supabase schema/migration, Edge Function deployment, Cloudflare Pages deployment, payment transaction, or Android signing key is changed by this branch.

## Release decision

This branch is a safer, testable release candidate, but the whole business system must not be labelled fully production-ready until the database migration history, Paymob live configuration, account 2FA, Auth leaked-password protection, and signed Android release requirements are resolved and verified.


## Additional storefront identifier hardening — 24 November 2026

A follow-up source review found that cart quantity/removal controls still interpolated product IDs and cart-item keys into inline JavaScript. These handlers have been replaced with inert `data-cart-action`, `data-product-id`, and `data-cart-item-key` attributes plus one delegated click handler bound to the cart container. The original increase, decrease, and remove actions are preserved. Product-card and favorites actions are also data-driven and covered by the same browser security regression suite.

The regression test now exercises hostile-looking category names, product IDs, and cart-item keys and verifies that the expected navigation/cart function arguments are preserved without executing injected code. On code commit `d771df8dd707bdf1618110469594a3441f2a7fb4`, the expanded stored-XSS regression, storefront JavaScript validation, disposable PostgreSQL integration tests, Worker syntax checks, and mobile regression all passed. The complete browser audit also passed: [run 45405229228](https://github.com/islamilnemrawi/Elory-store/actions/runs/45405229228).

A subsequent first-paint diagnostic-only commit `f7b4c9142818e228e3e38f0a161e1d6508825bf0` is undergoing its own complete browser and mobile regression run; do not infer its result from the prior commit's checks. No production deployment or database mutation was performed.
