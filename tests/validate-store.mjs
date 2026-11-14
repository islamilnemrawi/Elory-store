import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';

const root = process.cwd();
const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
  .map(match => match[1])
  .filter(source => source.trim());

assert.ok(scripts.length > 0, 'index.html must contain inline application scripts');
scripts.forEach((source, index) => {
  assert.doesNotThrow(
    () => new vm.Script(source, { filename: 'index.html:inline-' + (index + 1) }),
    'inline script ' + (index + 1) + ' must parse'
  );
});

assert.match(html, /Elory CMS settings load failed/);
assert.match(html, /attempt < 3/);
assert.match(html, /async function eloryFetchCatalogPage/);
assert.match(html, /params\.set\('limit'/);
assert.match(html, /params\.set\('offset'/);
assert.match(html, /count=exact/);
assert.match(html, /shopProductsPager/);
assert.match(html, /async function loadShopProducts/);
assert.match(html, /params\.append\('price', 'gte\.'/);
assert.match(html, /params\.append\('price', 'lte\.'/);
assert.match(html, /Elory hero image failed to load/);
assert.match(html, /naturalWidth>0/);
assert.match(html, /codResponse=await fetch/);
assert.match(html, /idempotency_key:order\.idempotency_key/);
assert.match(html, /getCheckoutIdempotencyKey\(order\)/);
assert.match(html, /code,sku/);
assert.doesNotMatch(html, /service_role|PAYMOB_SECRET_KEY/i, 'server secrets must never be embedded in storefront HTML');
assert.match(html, /function cacheCatalogProducts/);
assert.match(html, /slice\(-500\)/);

const submitStart = html.indexOf('async function submitOrder(event)');
const submitEnd = html.indexOf('function showOrderSuccessPage', submitStart);
assert.ok(submitStart >= 0 && submitEnd > submitStart, 'submitOrder boundaries must exist');
const submit = html.slice(submitStart, submitEnd);
assert.match(submit, /codResponse=await fetch/);
assert.doesNotMatch(submit, /\.from\(["']orders["']\)\.insert/, 'browser must not insert orders directly');

const edge = fs.readFileSync(path.join(root, 'supabase/functions/paymob/index.ts'), 'utf8');
assert.match(edge, /rpc\/elory_create_order_once/);
assert.match(edge, /rpc\/elory_claim_order_payment_session/);
assert.match(edge, /rpc\/elory_complete_order_payment_session/);
assert.match(edge, /paymobIntentionCreated/);
assert.match(edge, /Invalid Paymob HMAC/);
assert.match(edge, /retry_with_new_key/);
assert.match(edge, /ELORY_ALLOWED_ORIGIN/);
assert.match(edge, /notification_url: CALLBACK_URL/);
assert.match(edge, /paymobAmbiguous/);

const migration = fs.readFileSync(path.join(root, 'supabase/migrations/20261114000100_prelaunch_hardening.sql'), 'utf8');
assert.match(migration, /DO \$\$/);
assert.match(migration, /END;\n\$\$;/);
assert.match(migration, /pg_advisory_xact_lock/);
assert.match(migration, /FOR UPDATE/);
assert.match(migration, /inventory_reserved/);
assert.match(migration, /elory_restore_order_inventory/);
assert.match(migration, /elory_claim_order_payment_session/);
assert.match(migration, /uq_orders_idempotency_key/);
assert.match(migration, /idx_orders_pending_payment_expiry/);

const localSeed = fs.readFileSync(path.join(root, 'supabase/seed.sql'), 'utf8');
assert.match(localSeed, /ELORY LOAD TEST/);
assert.match(localSeed, /LOCAL TEST CENTER/);

const load = fs.readFileSync(path.join(root, 'tests/load/elory-prelaunch.js'), 'utf8');
assert.match(load, /dmttevcncsxzbamazmmq/);
assert.match(load, /ELORY_LOAD_TEST_APPROVED/);
assert.match(load, /stockRaceSuccess/);
assert.match(load, /stockRaceConflict/);
assert.match(load, /cash_on_delivery/);

console.log('Elory static validation PASSED');
console.log('Inline JavaScript scripts parsed:', scripts.length);
console.log('Pagination, CMS retries, hero image checks, order idempotency, inventory migration and load-test safeguards verified.');
