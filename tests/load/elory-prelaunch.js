import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Rate, Trend } from 'k6/metrics';

const base = (__ENV.SUPABASE_URL || '').replace(/\/+$/, '');
const anon = __ENV.SUPABASE_ANON_KEY || '';
const approved = __ENV.ELORY_LOAD_TEST_APPROVED === 'YES';
const raceMode = __ENV.RUN_STOCK_RACE === '1';
const paymobOnce = __ENV.RUN_PAYMOB_TEST_INTENTION === '1';

if (!approved) throw new Error('Set ELORY_LOAD_TEST_APPROVED=YES for a disposable local test only.');
if (!/^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/i.test(base)) {
  throw new Error('Safety stop: k6 may target localhost only. Production and remote Supabase URLs are blocked.');
}
if (base.includes('dmttevcncsxzbamazmmq')) throw new Error('Safety stop: Elory production project is blocked.');
if (!anon) throw new Error('SUPABASE_ANON_KEY is required.');

const headers = { apikey: anon, Authorization: 'Bearer ' + anon, 'Content-Type': 'application/json' };
const catalogLatency = new Trend('catalog_latency', true);
const searchLatency = new Trend('search_latency', true);
const filterLatency = new Trend('filter_latency', true);
const imageLatency = new Trend('sampled_image_latency', true);
const codLatency = new Trend('cod_latency', true);
const codFailureRate = new Rate('cod_failure_rate');
const codSuccess = new Counter('cod_success');
const stockRaceSuccess = new Counter('stockRaceSuccess');
const stockRaceConflict = new Counter('stockRaceConflict');

export const options = {
  scenarios: {
    elory: {
      executor: 'constant-vus',
      vus: Number(raceMode ? (__ENV.RACE_VUS || 100) : (__ENV.LOAD_VUS || 25)),
      duration: raceMode ? (__ENV.RACE_DURATION || '10s') : (__ENV.LOAD_DURATION || '120s')
    }
  },
  thresholds: raceMode
    ? { catalog_latency: ['p(95)<1500'], stockRaceSuccess: ['count==1'], stockRaceConflict: ['count>0'] }
    : {
        catalog_latency: ['p(95)<1500'],
        search_latency: ['p(95)<2000'],
        filter_latency: ['p(95)<1500'],
        cod_latency: ['p(95)<3000'],
        cod_failure_rate: ['rate<0.05']
      }
};

function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.floor(Math.random() * 16);
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function getJson(response, label) {
  if (response.status < 200 || response.status >= 300) {
    throw new Error(label + ' failed with HTTP ' + response.status + ': ' + response.body);
  }
  return response.json();
}

export function setup() {
  const productSku = raceMode ? 'ELORY-LOAD-RACE' : 'ELORY-LOAD-00001';
  const productUrl = base + '/rest/v1/products?select=id,name,price,image,stock,sku&sku=eq.' + productSku + '&limit=1';
  const productRows = getJson(http.get(productUrl, { headers }), 'Load-test product lookup');
  if (!Array.isArray(productRows) || productRows.length !== 1) throw new Error('Seed product missing. Run scripts/seed-10000.sh first.');

  const governorates = getJson(
    http.get(base + '/rest/v1/shipping_governorates?select=governorate,centers_enabled&active=eq.true&order=governorate.asc&limit=1', { headers }),
    'Shipping governorate lookup'
  );
  if (!Array.isArray(governorates) || governorates.length !== 1) throw new Error('No active shipping governorate is visible to local anon role.');

  let center = '';
  const centers = getJson(
    http.get(
      base + '/rest/v1/shipping_centers?select=center&active=eq.true&governorate=eq.' + encodeURIComponent(governorates[0].governorate) + '&order=center.asc&limit=1',
      { headers }
    ),
    'Shipping center lookup'
  );
  if (Array.isArray(centers) && centers.length) center = centers[0].center;
  return { product: productRows[0], governorate: governorates[0].governorate, center };
}

function catalogRequests(imageUrl) {
  const common = 'select=id,name,image,price,category,created_at&active=eq.true&order=created_at.desc,id.desc&limit=24';
  let response = http.get(base + '/rest/v1/products?' + common + '&offset=' + ((__ITER % 100) * 24), { headers });
  catalogLatency.add(response.timings.duration);
  check(response, { 'catalog page returns 200': r => r.status === 200 && Array.isArray(r.json()) });

  response = http.get(
    base + '/rest/v1/products?select=id,name,sku&active=eq.true&or=' +
    encodeURIComponent('(name.ilike.*Synthetic*,category.ilike.*Synthetic*,code.ilike.*Synthetic*,sku.ilike.*Synthetic*)') + '&limit=24',
    { headers }
  );
  searchLatency.add(response.timings.duration);
  check(response, { 'catalog search returns 200': r => r.status === 200 });

  response = http.get(base + '/rest/v1/products?select=id,name,price&active=eq.true&price=gte.100&price=lte.250&order=price.asc,id.asc&limit=24', { headers });
  filterLatency.add(response.timings.duration);
  check(response, { 'catalog price filter returns 200': r => r.status === 200 });

  if (__ITER % 10 === 0 && imageUrl) {
    const imageResponse = http.get(imageUrl, { timeout: '15s' });
    imageLatency.add(imageResponse.timings.duration);
    check(imageResponse, { 'sampled product image returns 200': r => r.status === 200 });
  }
}

function createOrder(data, paymentMethod = 'cash_on_delivery') {
  const payload = {
    type: 'order_payment',
    payment_method: paymentMethod,
    idempotency_key: uuid(),
    user_id: null,
    customer_access_token: uuid(),
    customer_name: 'Elory Local Load Test',
    phone: '01000000000',
    governorate: data.governorate,
    center: data.center,
    address: 'LOCAL LOAD TEST ONLY',
    notes: 'ELORY_LOAD_TEST: k6 synthetic request',
    items: [{
      product_id: data.product.id,
      name: data.product.name,
      price: Number(data.product.price),
      quantity: 1,
      image: data.product.image,
      color: null,
      size: null,
      code: data.product.sku
    }],
    subtotal: Number(data.product.price),
    shipping_cost: 0,
    total: Number(data.product.price),
    prime: false,
    prime_requested: false,
    coupon_code: null,
    coupon_discount: 0,
    coupon_free_shipping: false,
    prime_discount: 0,
    prime_free_shipping: false
  };
  const response = http.post(base + '/functions/v1/paymob', JSON.stringify(payload), { headers, timeout: '20s' });
  let body = {};
  try { body = response.json() || {}; } catch (_) {}
  return { response, body };
}

export default function (data) {
  catalogRequests(data.product.image || '');

  if (raceMode) {
    const result = createOrder(data);
    if (result.response.status === 200 && result.body.ok === true) {
      stockRaceSuccess.add(1);
      check(result.response, { 'stock race winner created': r => r.status === 200 });
    } else if (result.response.status === 409 &&
      (result.body.code === 'INVENTORY_UNAVAILABLE' || /الكمية المطلوبة|inventory|stock/i.test(result.response.body || ''))) {
      stockRaceConflict.add(1);
      check(result.response, { 'stock race loser receives inventory conflict': r => r.status === 409 });
    } else {
      check(result.response, { 'stock race returns success or inventory conflict': r => r.status === 200 || r.status === 409 });
    }
    sleep(0.05);
    return;
  }

  const started = Date.now();
  const result = createOrder(data);
  codLatency.add(Date.now() - started);
  const ok = result.response.status === 200 && result.body.ok === true;
  codFailureRate.add(!ok);
  if (ok) codSuccess.add(1);
  check(result.response, { 'COD order created': r => r.status === 200 && result.body.ok === true });

  if (paymobOnce && __VU === 1 && __ITER === 0) {
    const paymob = createOrder(data, 'card');
    check(paymob.response, { 'Paymob TEST intention created': r => r.status === 200 && !!paymob.body.checkout_url });
  }
  sleep(0.05);
}
