# Elory pre-launch hardening

## Implemented in this branch

- Catalog requests use bounded PostgREST pages (12–24 products per request), exact-count pagination, database-side search, category, price and sort filters, retry on transient errors, and deterministic ID tie-break ordering.
- Catalog results are retained in a bounded 500-product in-memory working cache so paging does not erase products needed by the cart/details layer.
- CMS settings log failures and retry up to three times. Hero images are checked for successful intrinsic dimensions; broken images are hidden and logged.
- COD and Paymob order creation use one server-side idempotent order RPC. The browser does not insert orders directly.
- A PostgreSQL trigger reserves base-product or variant stock atomically after the existing price/variant/shipping validation triggers run. The final-unit race is serialized on the product row.
- Cancelled, failed and expired pending orders restore the exact stock reservation. Paymob intention creation uses a private payment-session record to avoid duplicate chargeable intentions on retries. A network timeout, missing client secret, or ambiguous Paymob 5xx keeps the order reserved and the session in review instead of blindly creating another intention.
- A local synthetic seed creates 10,000 catalog products plus one one-unit race fixture. k6 scenarios measure page/search/filter, image, COD latency/failure, and concurrent stock reservation.

## Cost and production safety

No paid Supabase branch is created. No production migration, order, product, or payment is written by these scripts. The only remote setup action is a schema-only export to a local ignored file. The baseline contains schema definitions only, not customer/order rows or Storage objects. A tiny local seed adds one synthetic shipping governorate and center so the checkout tests do not depend on production shipping data.

The scripts block the known production project ID and require a localhost database URL before seeding, cleanup, or load tests. Local Supabase consumes local disk/CPU/network and Docker image downloads, not hosted Supabase quota. It does not incur a Supabase branch fee.

## Prerequisites

Install Supabase CLI, Docker Desktop (or compatible Docker runtime), Node.js 20+, PostgreSQL client psql, and k6 for load tests.

## 1. Export the schema-only baseline

From the repository root:

~~~bash
chmod +x scripts/*.sh
scripts/prepare-local-schema.sh
~~~

Type EXPORT-SCHEMA when prompted. The script links the CLI to the existing Elory project and exports only the public, private, and extensions schema definitions into:

supabase/migrations/20261114000000_remote_schema.sql

It refuses to overwrite an existing baseline. Review the exported SQL. This step does not run DDL on the remote database and does not copy customer or order data.

## 2. Start local Supabase and run integration tests

~~~bash
scripts/run-prelaunch-tests.sh
~~~

This starts the local stack, resets the local database only, applies the local schema baseline and hardening migration, parses the storefront inline JavaScript, checks required invariants, and runs transactional SQL integration tests. The SQL tests end with ROLLBACK.

The default local database URL is:

postgresql://postgres:postgres@127.0.0.1:54322/postgres

The SQL suite checks:
- COD order creation and idempotent replay (one order, one reservation).
- COD cancellation restores the original stock.
- Paymob payment-session claim and ready-session replay.
- Failed Paymob payment restores reserved stock.

## 3. Seed 10,000 synthetic products

Only after local integration tests pass:

~~~bash
ELORY_LOAD_TEST_APPROVED=YES scripts/seed-10000.sh
~~~

The seed creates 10,000 synthetic products with unique SKU/code values and one separate product with exactly one unit for the stock-race scenario. All synthetic rows are clearly prefixed ELORY-LOAD-.

Cleanup:

~~~bash
ELORY_LOAD_TEST_CLEANUP=YES scripts/cleanup-10000.sh
~~~

The cleanup removes synthetic orders first (allowing the inventory restore trigger to run), then synthetic products.

## 4. Run performance and concurrency tests

Start the local Paymob Edge Function with a local-only env file:

~~~bash
cp supabase/.env.test.example supabase/.env.test
supabase status -o env
~~~

Copy the local API_URL, ANON_KEY, and SERVICE_ROLE_KEY values from supabase status -o env into the ignored supabase/.env.test file. Keep all secret keys local; never paste them into index.html or commit them.

Then run:

~~~bash
supabase functions serve paymob --env-file supabase/.env.test
~~~

In another terminal, run the normal load test:

~~~bash
k6 run \
  -e SUPABASE_URL=http://127.0.0.1:54321 \
  -e SUPABASE_ANON_KEY=LOCAL_ANON_KEY \
  -e ELORY_LOAD_TEST_APPROVED=YES \
  -e LOAD_VUS=25 \
  -e LOAD_DURATION=120s \
  tests/load/elory-prelaunch.js
~~~

Increase gradually (10, 25, 50, then 100 VUs). The summary reports request latency and failure rate. Thresholds in the script are initial guardrails, not a guarantee of production capacity.

For the one-unit inventory race, re-run the seed script first so the race product returns to stock 1, then run:

~~~bash
k6 run \
  -e SUPABASE_URL=http://127.0.0.1:54321 \
  -e SUPABASE_ANON_KEY=LOCAL_ANON_KEY \
  -e ELORY_LOAD_TEST_APPROVED=YES \
  -e RUN_STOCK_RACE=1 \
  -e RACE_VUS=100 \
  -e RACE_DURATION=10s \
  tests/load/elory-prelaunch.js
~~~

Expected: exactly one successful order consumes the last unit; other attempts receive HTTP 409 inventory conflicts. The k6 threshold requires exactly one winner.

The script samples a synthetic product image every tenth iteration. Image latency is reported separately.

## 5. Paymob TEST

The local SQL tests validate payment-session idempotency, not a real Paymob network transaction. A full Paymob test requires TEST credentials from the merchant's Paymob account.

- Set PAYMOB_MODE=test and the PAYMOB_TEST_* keys in the ignored local env file.
- The current reviewed configuration has no Vodafone Cash TEST integration ID (0); keep wallet testing disabled until Paymob supplies one.
- To create one card TEST intention during the k6 run, set RUN_PAYMOB_TEST_INTENTION=1. This creates a pending local order and one intention; it does not complete a card payment.
- A real callback test requires a temporary public HTTPS tunnel to the local Edge Function. Set PAYMOB_NOTIFICATION_URL to that tunnel's /functions/v1/paymob URL and use a Paymob-published TEST card. Never use a real card.
- Verify the HMAC-signed callback and final order status before considering the payment path passed.

The function's ELORY_ALLOWED_ORIGIN, ELORY_SITE_URL, and PAYMOB_NOTIFICATION_URL are environment-overridable for local testing. Their production defaults remain the live storefront URL and Supabase function callback.

## Release gate

Do not deploy the migration or Edge Function to production until the local SQL tests, 10k seed, staged k6 runs, exact-one-winner stock race, Paymob card TEST intention, actual payment completion, HMAC callback, and security/performance advisor review all pass. A local load result is not a certified production traffic ceiling.

No claim is made here that Paymob's live transaction flow or production load has been tested. This branch is a reviewable candidate; no hosted migration or Edge Function deployment is performed.
