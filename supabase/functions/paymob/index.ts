 // Elory Paymob Edge Function
// Test / Live switch
// Prime: 300 EGP / 30 days / 10% / 6 free shipping orders / packaging
//
// Supports:
// 1) Prime subscription -> Card/VPC OR Vodafone Cash
// 2) Normal orders -> Card/VPC OR Vodafone Cash
// 3) Test/Live credentials and Integration IDs
//
// IMPORTANT:
// - No Paymob secret is exposed to the frontend.
// - Payment status is confirmed from the HMAC-verified callback.
// - Normal paid orders are created as "جاري الدفع" before redirect,
//   then changed to "طلب جديد" only after a successful callback.

import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

// ============================================================
// ENVIRONMENT
// ============================================================

const SUPABASE_URL =
  Deno.env.get("SUPABASE_URL") ||
  "https://dmttevcncsxzbamazmmq.supabase.co";

const ELORY_SERVICE_ROLE_KEY =
  Deno.env.get("ELORY_SERVICE_ROLE_KEY") ||
  Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ||
  "";

const PAYMOB_MODE =
  (Deno.env.get("PAYMOB_MODE") || "test").trim().toLowerCase();

if (PAYMOB_MODE !== "test" && PAYMOB_MODE !== "live") {
  throw new Error('PAYMOB_MODE must be "test" or "live".');
}

const LEGACY_API_KEY =
  Deno.env.get("PAYMOB_API_KEY") || "";

// Legacy fallback secrets.
// These are intentionally used only as fallbacks for TEST so an older
// deployment does not immediately break. LIVE uses the explicit
// PAYMOB_LIVE_* secrets.
const LEGACY_SECRET_KEY =
  Deno.env.get("PAYMOB_SECRET_KEY") || "";

const LEGACY_HMAC =
  Deno.env.get("PAYMOB_HMAC") || "";

const LEGACY_PUBLIC_KEY =
  Deno.env.get("PAYMOB_PUBLIC_KEY") || "";

// ============================================================
// TEST CREDENTIALS
// ============================================================

const PAYMOB_TEST_SECRET_KEY =
  Deno.env.get("PAYMOB_TEST_SECRET_KEY") ||
  LEGACY_SECRET_KEY;

const PAYMOB_TEST_HMAC =
  Deno.env.get("PAYMOB_TEST_HMAC") ||
  LEGACY_HMAC;

const PAYMOB_TEST_PUBLIC_KEY =
  Deno.env.get("PAYMOB_TEST_PUBLIC_KEY") ||
  LEGACY_PUBLIC_KEY;
const PAYMOB_TEST_API_KEY =
  Deno.env.get("PAYMOB_TEST_API_KEY") ||
  LEGACY_API_KEY;



const PAYMOB_TEST_INTEGRATION_ID =
  Number(
    Deno.env.get("PAYMOB_TEST_INTEGRATION_ID") ||
      "4475790",
  );

// Your current Test account has no Vodafone Cash wallet Integration ID
// in the configuration we reviewed. Keep this at 0 until Paymob gives
// you a real TEST wallet Integration ID.
const PAYMOB_TEST_WALLET_INTEGRATION_ID =
  Number(
    Deno.env.get("PAYMOB_TEST_WALLET_INTEGRATION_ID") ||
      "0",
  );

// ============================================================
// LIVE CREDENTIALS
// ============================================================

const PAYMOB_LIVE_SECRET_KEY =
  Deno.env.get("PAYMOB_LIVE_SECRET_KEY") || "";

const PAYMOB_LIVE_HMAC =
  Deno.env.get("PAYMOB_LIVE_HMAC") || "";

const PAYMOB_LIVE_PUBLIC_KEY =
  Deno.env.get("PAYMOB_LIVE_PUBLIC_KEY") || "";

const PAYMOB_LIVE_API_KEY =
  Deno.env.get("PAYMOB_LIVE_API_KEY") ||
  LEGACY_API_KEY;



const PAYMOB_LIVE_INTEGRATION_ID =
  Number(
    Deno.env.get("PAYMOB_LIVE_INTEGRATION_ID") ||
      "4475854",
  );

const PAYMOB_LIVE_WALLET_INTEGRATION_ID =
  Number(
    Deno.env.get("PAYMOB_LIVE_WALLET_INTEGRATION_ID") ||
      "4475853",
  );

// ============================================================
// ACTIVE PAYMOB CONFIG
// ============================================================

const isLive = PAYMOB_MODE === "live";

const PAYMOB_API_KEY = isLive
  ? PAYMOB_LIVE_API_KEY
  : PAYMOB_TEST_API_KEY;

const PAYMOB_SECRET_KEY = isLive
  ? PAYMOB_LIVE_SECRET_KEY
  : PAYMOB_TEST_SECRET_KEY;

const PAYMOB_HMAC = isLive
  ? PAYMOB_LIVE_HMAC
  : PAYMOB_TEST_HMAC;

const PAYMOB_PUBLIC_KEY = isLive
  ? PAYMOB_LIVE_PUBLIC_KEY
  : PAYMOB_TEST_PUBLIC_KEY;

const CARD_INTEGRATION_ID = isLive
  ? PAYMOB_LIVE_INTEGRATION_ID
  : PAYMOB_TEST_INTEGRATION_ID;

const WALLET_INTEGRATION_ID = isLive
  ? PAYMOB_LIVE_WALLET_INTEGRATION_ID
  : PAYMOB_TEST_WALLET_INTEGRATION_ID;

// ============================================================
// PAYMOB
// ============================================================

const PAYMOB_BASE_URL =
  "https://accept.paymob.com";

const PAYMOB_INTENTION_URL =
  `${PAYMOB_BASE_URL}/v1/intention/`;

const SITE_URL =
  "https://islamilnemrawi.github.io/Elory-store/";

const CALLBACK_URL =
  `${SUPABASE_URL}/functions/v1/paymob`;

const ALLOWED_ORIGIN =
  "https://islamilnemrawi.github.io";

// ============================================================
// ELORY PRIME
// ============================================================

const PRIME_PRICE = 300;
const PRIME_DURATION_DAYS = 30;
const PRIME_FREE_SHIPPING_LIMIT = 6;
const PRIME_DISCOUNT_PERCENT = 10;
const PRIME_PACKAGING_ENABLED = true;

type EloryPrimeConfig = {
  enabled: boolean; price: number; durationDays: number;
  freeShippingOrdersCount: number; discountPercent: number;
  packagingEnabled: boolean; themeEnabled: boolean; features: string[];
};

// ============================================================
// CORS
// ============================================================

const corsHeaders = {
  "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods":
    "POST, OPTIONS",
  "Content-Type": "application/json",
};

// ============================================================
// HELPERS
// ============================================================

function json(
  body: unknown,
  status = 200,
) {
  return new Response(
    JSON.stringify(body),
    {
      status,
      headers: corsHeaders,
    },
  );
}

function addDays(
  date: Date,
  days: number,
) {
  const result = new Date(date);
  result.setUTCDate(
    result.getUTCDate() + days,
  );
  return result;
}

function randomReference() {
  return [
    "ELORY",
    isLive ? "LIVE" : "TEST",
    Date.now().toString(36),
    crypto.randomUUID().slice(0, 8),
  ].join("-");
}

function normalizePhone(phone: string) {
  let value = String(phone || "").trim();

  value = value.replace(/\s+/g, "");

  if (value.startsWith("01")) {
    value = "+2" + value;
  }

  if (value.startsWith("201")) {
    value = "+" + value;
  }

  return value;
}

function cleanText(
  value: unknown,
  fallback = "",
) {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function normalizePaymentMethod(
  value: unknown,
) {
  const method =
    String(value || "").trim().toLowerCase();

  if (
    method === "card" ||
    method === "visa" ||
    method === "mastercard"
  ) {
    return "card";
  }

  if (
    method === "vodafone_cash" ||
    method === "vodafone-cash" ||
    method === "vodafone"
  ) {
    return "vodafone_cash";
  }

  if (
    method === "cash_on_delivery" ||
    method === "cod"
  ) {
    return "cash_on_delivery";
  }

  return method;
}

function getFirstName(
  customerName: string,
) {
  return (
    customerName.split(/\s+/).filter(Boolean)[0] ||
    "Elory"
  );
}

function getLastName(
  customerName: string,
) {
  const parts =
    customerName.split(/\s+/).filter(Boolean);

  return (
    parts.slice(1).join(" ") ||
    "Customer"
  );
}

function isUuid(value: unknown) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
    .test(String(value || ""));
}

// ============================================================
// SUPABASE REST
// ============================================================

async function supabaseRequest(
  path: string,
  options: RequestInit = {},
) {
  if (!ELORY_SERVICE_ROLE_KEY) {
    throw new Error(
      "Missing ELORY_SERVICE_ROLE_KEY / SUPABASE_SERVICE_ROLE_KEY",
    );
  }

  const response = await fetch(
    `${SUPABASE_URL}/rest/v1/${path}`,
    {
      ...options,
      headers: {
        apikey: ELORY_SERVICE_ROLE_KEY,
        Authorization:
          `Bearer ${ELORY_SERVICE_ROLE_KEY}`,
        "Content-Type":
          "application/json",
        Prefer:
          "return=representation",
        ...(options.headers || {}),
      },
    },
  );

  const text =
    await response.text();

  let data: unknown = null;

  try {
    data =
      text
        ? JSON.parse(text)
        : null;
  } catch {
    data = text;
  }

  if (!response.ok) {
    throw new Error(
      `Supabase ${response.status}: ${text}`,
    );
  }

  return data;
}

function boundedNumber(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
}

type PaymentMethodAvailability = {
  card: boolean;
  wallet: boolean;
  cod: boolean;
};

async function getPaymentMethodAvailability(): Promise<PaymentMethodAvailability> {
  const rows = await supabaseRequest(
    "site_customizations?id=eq.1&select=config&limit=1",
    { method: "GET" },
  ) as any[];
  const methods = Array.isArray(rows?.[0]?.config?.paymentMethods?.methods)
    ? rows[0].config.paymentMethods.methods
    : [];
  const isEnabled = (...keys: string[]) => {
    const item = methods.find((entry: any) =>
      keys.includes(String(entry?.key || "").trim().toLowerCase())
    );
    // Keep existing checkout behavior for older configs that predate dashboard switches.
    return item ? item.isEnabled !== false : true;
  };
  return {
    card: isEnabled("credit_card", "card"),
    wallet: isEnabled("vodafone_cash"),
    cod: isEnabled("cod", "cash_on_delivery"),
  };
}

async function getPrimeConfig(): Promise<EloryPrimeConfig> {
  const rows = await supabaseRequest(
    "site_customizations?id=eq.1&select=config&limit=1",
    { method: "GET" },
  ) as any[];
  const prime = rows?.[0]?.config?.prime || {};
  const features = Array.isArray(prime.features)
    ? prime.features.filter((feature: unknown) => typeof feature === "string")
        .map((feature: string) => feature.trim()).filter(Boolean).slice(0, 12)
    : [];
  const enabled = prime.enabled === undefined || prime.enabled === null
    ? true
    : prime.enabled === true || String(prime.enabled).trim().toLowerCase() === "true";
  return {
    enabled,
    price: boundedNumber(prime.price, PRIME_PRICE, 0.01, 1000000),
    durationDays: Math.round(boundedNumber(prime.durationDays, PRIME_DURATION_DAYS, 1, 3650)),
    freeShippingOrdersCount: Math.round(boundedNumber(prime.freeShippingOrdersCount, PRIME_FREE_SHIPPING_LIMIT, 0, 100)),
    discountPercent: boundedNumber(prime.discountPercent, PRIME_DISCOUNT_PERCENT, 0, 100),
    packagingEnabled: String(prime.packagingFeature || "").trim().length > 0,
    themeEnabled: String(prime.themeFeature || "").trim().length > 0,
    features,
  };
}

async function getAuthenticatedUserId(request: Request): Promise<string | null> {
  const authorization = request.headers.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);
  if (!match || !ELORY_SERVICE_ROLE_KEY) return null;

  try {
    const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
      method: "GET",
      headers: {
        apikey: ELORY_SERVICE_ROLE_KEY,
        Authorization: `Bearer ${match[1]}`,
      },
    });
    if (!response.ok) return null;
    const user = await response.json().catch(() => null);
    return isUuid(user?.id) ? user.id : null;
  } catch {
    return null;
  }
}

// ============================================================
// PRIME LOOKUP
// ============================================================

async function getActivePrime(
  userId: string,
) {
  const rows = await supabaseRequest(
    `prime_subscriptions?user_id=eq.${encodeURIComponent(userId)}&active=eq.true&status=eq.active&order=expires_at.desc&limit=1`,
    {
      method: "GET",
    },
  ) as any[];

  if (!rows || rows.length === 0) {
    return null;
  }

  const prime = rows[0];

  if (
    !prime.expires_at ||
    new Date(prime.expires_at).getTime() <=
      Date.now()
  ) {
    await supabaseRequest(
      `prime_subscriptions?id=eq.${encodeURIComponent(prime.id)}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          active: false,
          status: "expired",
        }),
      },
    );

    return null;
  }

  return prime;
}

// ============================================================
// PRIME BY PAYMENT REFERENCE
// ============================================================

async function findPrimeByReference(
  paymentReference: string,
) {
  const rows = await supabaseRequest(
    `prime_subscriptions?payment_reference=eq.${encodeURIComponent(paymentReference)}&order=created_at.desc&limit=1`,
    {
      method: "GET",
    },
  ) as any[];

  return rows?.[0] || null;
}

// ============================================================
// CREATE PENDING PRIME
// ============================================================

async function createPendingPrime(params: {
  userId: string;
  customerName: string;
  phone: string;
  email: string;
  paymentReference: string;
  primeConfig: EloryPrimeConfig;
}) {
  const pendingStartedAt =
    new Date();

  const pendingExpiresAt =
    addDays(
      pendingStartedAt,
      params.primeConfig.durationDays,
    );

  const existing =
    await findPrimeByReference(
      params.paymentReference,
    );

  if (existing) {
    return existing;
  }

  const activePrime =
    await getActivePrime(
      params.userId,
    );

  if (activePrime) {
    throw new Error(
      "Prime subscription is already active.",
    );
  }

  const rows =
    await supabaseRequest(
      "prime_subscriptions",
      {
        method: "POST",
        body: JSON.stringify({
          user_id:
            params.userId,

          started_at:
            pendingStartedAt.toISOString(),

          expires_at:
            pendingExpiresAt.toISOString(),

          active: false,

          created_at:
            pendingStartedAt.toISOString(),

          free_shipping_limit:
            params.primeConfig.freeShippingOrdersCount,

          free_shipping_used: 0,

          discount_percent:
            params.primeConfig.discountPercent,

          packaging_enabled:
            params.primeConfig.packagingEnabled,

          price:
            params.primeConfig.price,

          duration_days:
            params.primeConfig.durationDays,

          theme_enabled:
            params.primeConfig.themeEnabled,

          features:
            params.primeConfig.features,

          payment_reference:
            params.paymentReference,

          status: "pending",
        }),
      },
    ) as any[];

  return rows?.[0] || null;
}

// ============================================================
// ACTIVATE PRIME
// ============================================================

async function activatePrime(
  primeId: string,
  paymentReference: string,
) {
  const startedAt =
    new Date();

  const existingRows = await supabaseRequest(
    "prime_subscriptions?id=eq." + encodeURIComponent(primeId) + "&select=duration_days&limit=1",
    { method: "GET" },
  ) as any[];
  const durationDays = Math.round(boundedNumber(existingRows?.[0]?.duration_days, PRIME_DURATION_DAYS, 1, 3650));
  const expiresAt = addDays(startedAt, durationDays);

  const rows =
    await supabaseRequest(
      `prime_subscriptions?id=eq.${encodeURIComponent(primeId)}`,
      {
        method: "PATCH",
        body: JSON.stringify({
          started_at:
            startedAt.toISOString(),

          expires_at:
            expiresAt.toISOString(),

          active: true,

          status: "active",

          payment_confirmed: true,

          free_shipping_used: 0,

          payment_reference:
            paymentReference,
        }),
      },
    ) as any[];

  return rows?.[0] || null;
}

// ============================================================
// MARK PRIME PAYMENT FAILED
// ============================================================

async function markPrimeFailed(
  primeId: string,
) {
  return await supabaseRequest(
    `prime_subscriptions?id=eq.${encodeURIComponent(primeId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({
        active: false,
        status: "failed",
      }),
    },
  );
}

// ============================================================
// NORMAL ORDER HELPERS
// ============================================================

async function findOrderById(
  orderId: string,
) {
  if (!isUuid(orderId)) {
    return null;
  }

  const rows =
    await supabaseRequest(
      `orders?id=eq.${encodeURIComponent(orderId)}&limit=1`,
      {
        method: "GET",
      },
    ) as any[];

  return rows?.[0] || null;
}

async function redeemCouponForOrder(order: any) {
  const orderId = String(order?.id || "").trim();
  const couponCode = String(order?.coupon_code || "").trim();
  if (!isUuid(orderId) || !couponCode) return false;

  const coupons = await supabaseRequest(
    `coupons?code=eq.${encodeURIComponent(couponCode)}&select=id&limit=1`,
    { method: "GET" },
  ) as any[];

  const couponId = coupons?.[0]?.id;
  if (!couponId) return false;

  const result = await supabaseRequest(
    "rpc/redeem_coupon",
    {
      method: "POST",
      body: JSON.stringify({
        p_coupon_id: couponId,
        p_order_id: orderId,
      }),
    },
  );

  return result === true;
}

async function createPendingOrder(
  order: any,
) {
  const payload = {
    user_id:
      order?.user_id || null,

    customer_user_id:
      order?.user_id || null,

    // Keep the customer token supplied by the storefront so the
    // existing customer-order history RPC can continue to see all
    // orders for the same browser/customer. Generate one only when
    // an older client did not send a token.
    customer_access_token:
      cleanText(order?.customer_access_token) ||
      crypto.randomUUID(),

    customer_name:
      cleanText(
        order?.customer_name,
        "Elory Customer",
      ),

    phone:
      cleanText(order?.phone),

    governorate:
      cleanText(order?.governorate),

    center:
      cleanText(order?.center),

    address:
      cleanText(order?.address),

    notes:
      cleanText(order?.notes),

    items:
      Array.isArray(order?.items)
        ? order.items
        : [],

    subtotal:
      Number(order?.subtotal || 0),

    shipping_cost:
      Number(order?.shipping_cost || 0),

    total:
      Number(order?.total || 0),

    payment_method:
      normalizePaymentMethod(
        order?.payment_method,
      ),

    status:
      "جاري الدفع",

    prime:
      Boolean(order?.prime),

    prime_requested:
      Boolean(order?.prime_requested),

    coupon_code:
      order?.coupon_code || null,

    coupon_discount:
      Number(order?.coupon_discount || 0),

    coupon_free_shipping:
      Boolean(order?.coupon_free_shipping),

    prime_discount:
      Number(order?.prime_discount || 0),

    prime_free_shipping:
      Boolean(order?.prime_free_shipping),

    profit:
      Number(order?.profit || 0),
  };

  const rows =
    await supabaseRequest(
      "orders",
      {
        method: "POST",
        body:
          JSON.stringify(payload),
      },
    ) as any[];

  const created =
    rows?.[0];

  if (!created?.id) {
    throw new Error(
      "Supabase did not return the created order ID.",
    );
  }

  return created;
}

async function updateOrderPaymentStatus(
  orderId: string,
  status: string,
) {
  if (!isUuid(orderId)) {
    return null;
  }

  const rows =
    await supabaseRequest(
      `orders?id=eq.${encodeURIComponent(orderId)}`,
      {
        method: "PATCH",
        body:
          JSON.stringify({
            status,
          }),
      },
    ) as any[];

  return rows?.[0] || null;
}

// ============================================================
// HMAC
// ============================================================

function getNested(
  obj: any,
  path: string[],
) {
  let value = obj;

  for (const key of path) {
    if (
      value === null ||
      value === undefined
    ) {
      return "";
    }

    value =
      value[key];
  }

  return value ?? "";
}

function hmacValue(
  obj: any,
) {
  const fields = [
    ["amount_cents"],
    ["created_at"],
    ["currency"],
    ["error_occured"],
    ["has_parent_transaction"],
    ["id"],
    ["integration_id"],
    ["is_3d_secure"],
    ["is_auth"],
    ["is_capture"],
    ["is_refunded"],
    ["is_standalone_payment"],
    ["is_voided"],
    ["order", "id"],
    ["owner"],
    ["pending"],
    ["source_data", "pan"],
    ["source_data", "sub_type"],
    ["source_data", "type"],
    ["success"],
  ];

  return fields
    .map((field) =>
      String(
        getNested(
          obj,
          field,
        ),
      )
    )
    .join("");
}

function hexFromBytes(
  bytes: Uint8Array,
) {
  return Array.from(bytes)
    .map((b) =>
      b.toString(16).padStart(2, "0")
    )
    .join("");
}

async function calculateHmac(
  payload: string,
  secret: string,
) {
  const encoder =
    new TextEncoder();

  const key =
    await crypto.subtle.importKey(
      "raw",
      encoder.encode(secret),
      {
        name: "HMAC",
        hash: "SHA-512",
      },
      false,
      ["sign"],
    );

  const signature =
    await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(payload),
    );

  return hexFromBytes(
    new Uint8Array(signature),
  );
}

function timingSafeEqual(
  a: string,
  b: string,
) {
  if (a.length !== b.length) {
    return false;
  }

  let result = 0;

  for (
    let i = 0;
    i < a.length;
    i++
  ) {
    result |=
      a.charCodeAt(i) ^
      b.charCodeAt(i);
  }

  return result === 0;
}

async function verifyPaymobCallback(
  obj: any,
  receivedHmac: string,
) {
  if (!PAYMOB_HMAC) {
    throw new Error(
      "Missing PAYMOB_HMAC for current Paymob mode.",
    );
  }

  if (!receivedHmac) {
    return false;
  }

  const value =
    hmacValue(obj);

  const expected =
    await calculateHmac(
      value,
      PAYMOB_HMAC,
    );

  return timingSafeEqual(
    expected.toLowerCase(),
    receivedHmac.toLowerCase(),
  );
}

// ============================================================
// PAYMOB CALLBACK
// ============================================================

async function handlePaymobCallback(
  request: Request,
) {
  const body =
    await request.json();

  const obj =
    body?.obj;

  if (!obj) {
    return json(
      {
        ok: false,
        error:
          "Missing transaction object.",
      },
      400,
    );
  }

  const url =
    new URL(request.url);

  const receivedHmac =
    url.searchParams.get("hmac") ||
    "";

  const valid =
    await verifyPaymobCallback(
      obj,
      receivedHmac,
    );

  if (!valid) {
    return json(
      {
        ok: false,
        error:
          "Invalid Paymob HMAC.",
      },
      401,
    );
  }

  // HMAC proves the callback came from Paymob. These additional checks
  // prove that the transaction itself is a successful, non-pending EGP
  // payment for the integration configured for this flow.
  if (String(obj?.currency || "").toUpperCase() !== "EGP") {
    return json({ ok: false, error: "Invalid payment currency." }, 400);
  }

  if (obj?.pending === true) {
    return json({ ok: true, status: "payment_pending" });
  }

  if (obj?.is_refunded === true || obj?.is_voided === true || obj?.is_void === true) {
    return json({ ok: true, status: "payment_reversed" });
  }

  const merchantOrderId =
    obj?.order?.merchant_order_id ||
    obj?.merchant_order_id ||
    "";

  // ----------------------------------------------------------
  // PRIME CALLBACK
  // ----------------------------------------------------------

  if (
    String(merchantOrderId)
      .startsWith("ELORY-LIVE-") ||
    String(merchantOrderId)
      .startsWith("ELORY-TEST-")
  ) {
    const prime =
      await findPrimeByReference(
        merchantOrderId,
      );

    if (!prime) {
      return json(
        {
          ok: false,
          error:
            "Prime payment reference not found.",
          reference:
            merchantOrderId,
        },
        404,
      );
    }

    const amountCents =
      Number(
        obj?.amount_cents || 0,
      );

    const expectedPrimeAmount = Math.round(Number(prime.price ?? PRIME_PRICE) * 100);
    if (!Number.isSafeInteger(expectedPrimeAmount) || amountCents !== expectedPrimeAmount) {
      return json({ ok: false, error: "Invalid Prime payment amount.", expected: expectedPrimeAmount, received: amountCents }, 400);
    }

    const primeIntegrationId = Number(obj?.integration_id || 0);
    const validPrimeIntegrations = [
      CARD_INTEGRATION_ID,
      WALLET_INTEGRATION_ID,
    ].filter((id) => Number(id) > 0);

    if (!validPrimeIntegrations.includes(primeIntegrationId)) {
      return json({
        ok: false,
        error: "Unexpected Paymob integration for Prime.",
      }, 400);
    }

    if (
      obj?.success !== true ||
      obj?.error_occured === true
    ) {
      await markPrimeFailed(
        prime.id,
      );

      return json({
        ok: true,
        status:
          "payment_failed",
      });
    }

    if (
      prime.active === true &&
      prime.status === "active"
    ) {
      return json({
        ok: true,
        status:
          "already_active",
        prime_id:
          prime.id,
      });
    }

    const activated =
      await activatePrime(
        prime.id,
        merchantOrderId,
      );

    return json({
      ok: true,
      status:
        "prime_activated",
      prime:
        activated,
    });
  }

  // ----------------------------------------------------------
  // NORMAL ORDER CALLBACK
  // ----------------------------------------------------------

  if (!merchantOrderId) {
    return json(
      {
        ok: false,
        error:
          "Missing merchant_order_id.",
      },
      400,
    );
  }

  const order =
    await findOrderById(
      String(merchantOrderId),
    );

  if (!order) {
    return json(
      {
        ok: false,
        error:
          "Normal order not found.",
        reference:
          merchantOrderId,
      },
      404,
    );
  }

  const expectedAmount =
    Math.round(
      Number(order.total || 0) *
        100,
    );

  const receivedAmount =
    Number(
      obj?.amount_cents || 0,
    );

  if (
    !Number.isFinite(expectedAmount) ||
    expectedAmount <= 0
  ) {
    return json(
      {
        ok: false,
        error:
          "Invalid local order amount.",
      },
      400,
    );
  }

  if (
    receivedAmount !==
    expectedAmount
  ) {
    return json(
      {
        ok: false,
        error:
          "Payment amount does not match order total.",
        expected:
          expectedAmount,
        received:
          receivedAmount,
      },
      400,
    );
  }

  const expectedIntegration =
    normalizePaymentMethod(order.payment_method) === "vodafone_cash"
      ? WALLET_INTEGRATION_ID
      : CARD_INTEGRATION_ID;

  if (Number(obj?.integration_id || 0) !== Number(expectedIntegration || 0)) {
    return json({
      ok: false,
      error: "Unexpected Paymob integration for this order.",
    }, 400);
  }

  // Idempotent success.
  if (
    String(order.status || "") ===
    "طلب جديد"
  ) {
    await redeemCouponForOrder(order);
    return json({
      ok: true,
      status:
        "already_confirmed",
      order_id:
        order.id,
    });
  }

  if (
    obj?.success !== true ||
    obj?.error_occured === true
  ) {
    await updateOrderPaymentStatus(
      order.id,
      "فشل الدفع",
    );

    return json({
      ok: true,
      status:
        "payment_failed",
      order_id:
        order.id,
    });
  }

  const updated =
    await updateOrderPaymentStatus(
      order.id,
      "طلب جديد",
    );

  await redeemCouponForOrder(order);

  return json({
    ok: true,
    status:
      "order_payment_confirmed",
    order_id: order.id,
  });
}

// ============================================================
// CREATE PRIME INTENTION
// ============================================================

async function createPrimeIntention(
  body: any,
) {
  if (!PAYMOB_SECRET_KEY) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Secret Key.`,
    );
  }

  if (!PAYMOB_PUBLIC_KEY) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Public Key.`,
    );
  }

  if (
    !CARD_INTEGRATION_ID ||
    CARD_INTEGRATION_ID <= 0
  ) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Card/VPC Integration ID.`,
    );
  }

  const userId =
    String(
      body?.user_id || "",
    ).trim();

  if (!userId) {
    throw new Error(
      "Prime requires a logged-in user.",
    );
  }

  const customerName =
    cleanText(
      body?.customer_name,
      "Elory Customer",
    );

  const email =
    cleanText(
      body?.email,
    );

  const phone =
    normalizePhone(
      String(
        body?.phone || "",
      ),
    );

  if (!phone) {
    throw new Error(
      "Phone number is required.",
    );
  }

  const activePrime =
    await getActivePrime(
      userId,
    );

  if (activePrime) {
    throw new Error(
      "Prime is already active for this account.",
    );
  }

  const primeConfig = await getPrimeConfig();
  if (!primeConfig.enabled) throw new Error("اشتراكات Elory Prime غير متاحة حاليًا.");
  const amountCents = Math.round(primeConfig.price * 100);
  if (!Number.isSafeInteger(amountCents) || amountCents <= 0) throw new Error("Prime price configuration is invalid.");

  const paymentReference =
    randomReference();

  await createPendingPrime({
    userId,
    customerName,
    phone,
    email,
    paymentReference,
    primeConfig,
  });

  const intentionBody = {
    amount:
      amountCents,

    currency:
      "EGP",

    // Prime supports the currently configured Card/Visa and
    // Vodafone Cash integrations. Final activation is always
    // server-verified, so it does not trust the browser redirect.
    payment_methods: [
      CARD_INTEGRATION_ID,
      ...(WALLET_INTEGRATION_ID > 0 && body?.allow_wallet_payment !== false
        ? [WALLET_INTEGRATION_ID]
        : []),
    ],

    items: [
      {
        name:
          "Elory Prime - " + primeConfig.durationDays + " Days",

        amount:
          amountCents,

        description:
          "Elory Prime subscription for " + primeConfig.durationDays + " days",

        quantity: 1,
      },
    ],

    billing_data: {
      apartment: "NA",
      first_name:
        getFirstName(
          customerName,
        ),
      last_name:
        getLastName(
          customerName,
        ),
      street: "NA",
      building: "NA",
      phone_number:
        phone,
      city: "Cairo",
      country: "EG",
      email:
        email ||
        "customer@elory.store",
      floor: "NA",
      state: "Cairo",
      postal_code: "NA",
    },

    extras: {
      store:
        "Elory",

      type:
        "prime_subscription",

      prime:
        true,

      prime_only:
        true,

      user_id:
        userId,

      payment_reference:
        paymentReference,

      mode:
        PAYMOB_MODE,
    },

    special_reference:
      paymentReference,

    expiration:
      3600,

    ...(WALLET_INTEGRATION_ID > 0
      ? {}
      : { notification_url: CALLBACK_URL }),

    redirection_url:
      SITE_URL,
  };

  return await sendIntention(
    intentionBody,
  );
}

// ============================================================
// CREATE NORMAL ORDER INTENTION
// ============================================================

async function createNormalOrderIntention(
  body: any,
) {
  if (!PAYMOB_SECRET_KEY) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Secret Key.`,
    );
  }

  if (!PAYMOB_PUBLIC_KEY) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Public Key.`,
    );
  }

  const selectedMethod =
    normalizePaymentMethod(
      body?.payment_method,
    );

  if (
    selectedMethod !== "card" &&
    selectedMethod !== "vodafone_cash"
  ) {
    throw new Error(
      "Unsupported payment method. Use card or vodafone_cash.",
    );
  }

  const integrationId =
    selectedMethod === "card"
      ? CARD_INTEGRATION_ID
      : WALLET_INTEGRATION_ID;

  if (
    !integrationId ||
    integrationId <= 0
  ) {
    if (
      selectedMethod ===
      "vodafone_cash"
    ) {
      throw new Error(
        `Vodafone Cash is not configured for ${isLive ? "Live" : "Test"} mode. Add PAYMOB_${isLive ? "LIVE" : "TEST"}_WALLET_INTEGRATION_ID with a valid Vodafone Cash Integration ID.`,
      );
    }

    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} Card/VPC Integration ID.`,
    );
  }

  const customerName =
    cleanText(
      body?.customer_name,
      "Elory Customer",
    );

  const email =
    cleanText(
      body?.email,
    );

  const phone =
    normalizePhone(
      String(
        body?.phone || "",
      ),
    );

  if (!phone) {
    throw new Error(
      "Phone number is required.",
    );
  }

  const requestedItems =
    Array.isArray(body?.items)
      ? body.items
      : [];

  if (requestedItems.length === 0) {
    throw new Error(
      "Order items are required.",
    );
  }

  // The database recalculates product prices, Prime discounts,
  // coupon discounts, shipping and the final total before insert.
  // Paymob must charge that authoritative database total, never
  // the amount supplied by the browser.
  const localOrder =
    await createPendingOrder({
      ...body,
      payment_method:
        selectedMethod,
    });

  const customerOrderId =
    String(localOrder.id);

  try {
    const total = Number(localOrder.total || 0);
    if (!Number.isFinite(total) || total <= 0) {
      await updateOrderPaymentStatus(customerOrderId, "فشل الدفع");
      throw new Error("The server-calculated order total is invalid.");
    }

    const amountCents = Math.round(total * 100);
    if (!Number.isSafeInteger(amountCents) || amountCents <= 0) {
      await updateOrderPaymentStatus(customerOrderId, "فشل الدفع");
      throw new Error("The server-calculated payment amount is invalid.");
    }

    const items = Array.isArray(localOrder.items)
      ? localOrder.items
      : requestedItems;

    const intentionBody = {
      amount:
        amountCents,

      currency:
        "EGP",

      // The checkout is already filtered by the customer's
      // selected payment method, so we send exactly one
      // Integration ID per intention.
      payment_methods: [
        integrationId,
      ],

      // Paymob requires the sum of item amounts to equal the
      // intention amount. The Elory total may include shipping,
      // coupons, and Prime adjustments, so send one aggregate
      // Paymob line item for the exact payable total. The full
      // product breakdown remains stored in Supabase orders.items.
      items: [
        {
          name: "Elory Order",
          amount: amountCents,
          description: items
            .map((item: any) =>
              cleanText(item?.name, "Elory Product"),
            )
            .join(" | ")
            .slice(0, 255),
          quantity: 1,
        },
      ],

      billing_data: {
        apartment:
          "NA",

        first_name:
          getFirstName(
            customerName,
          ),

        last_name:
          getLastName(
            customerName,
          ),

        street:
          cleanText(
            body?.address,
            "NA",
          ),

        building:
          "NA",

        phone_number:
          phone,

        city:
          cleanText(
            body?.governorate,
            "Cairo",
          ),

        country:
          "EG",

        email:
          email ||
          "customer@elory.store",

        floor:
          "NA",

        state:
          cleanText(
            body?.governorate,
            "Cairo",
          ),

        postal_code:
          "NA",
      },

      extras: {
        store:
          "Elory",

        type:
          "normal_order",

        order_id:
          customerOrderId,

        payment_method:
          selectedMethod,

        mode:
          PAYMOB_MODE,
      },

      special_reference:
        customerOrderId,

      expiration:
        3600,

      // Paymob's current Intention API documents notification_url
      // for card integrations. Therefore it is sent for Card.
      // Wallet uses the redirection URL and does not depend on
      // notification_url being supported by a wallet Integration ID.
      ...(selectedMethod === "card"
        ? {
            notification_url:
              CALLBACK_URL,
          }
        : {}),

      redirection_url:
        SITE_URL,
    };

    const result =
      await sendIntention(
        intentionBody,
      );

    return {
      ...result,

      order_id:
        customerOrderId,

      payment_method:
        selectedMethod,
    };
  } catch (error) {
    // Payment intention creation failed before the customer
    // reached Paymob. Do not leave a fake active order.
    try {
      await updateOrderPaymentStatus(
        customerOrderId,
        "فشل إنشاء الدفع",
      );
    } catch (updateError) {
      console.error(
        "Could not mark failed payment order:",
        updateError,
      );
    }

    throw error;
  }
}

// ============================================================
// SEND PAYMOB INTENTION
// ============================================================

async function sendIntention(
  intentionBody: any,
) {
  const response =
    await fetch(
      PAYMOB_INTENTION_URL,
      {
        method:
          "POST",

        headers: {
          Authorization:
            `Token ${PAYMOB_SECRET_KEY}`,

          "Content-Type":
            "application/json",
        },

        body:
          JSON.stringify(
            intentionBody,
          ),
      },
    );

  const text =
    await response.text();

  let result: any = null;

  try {
    result =
      text
        ? JSON.parse(text)
        : null;
  } catch {
    result = {
      raw: text,
    };
  }

  if (!response.ok) {
    throw new Error(
      `Paymob ${response.status}: ${text}`,
    );
  }

  const clientSecret =
    result?.client_secret;

  if (!clientSecret) {
    throw new Error(
      "Paymob did not return client_secret.",
    );
  }

  const checkoutUrl =
    `${PAYMOB_BASE_URL}/unifiedcheckout/` +
    `?publicKey=${encodeURIComponent(
      PAYMOB_PUBLIC_KEY,
    )}` +
    `&clientSecret=${encodeURIComponent(
      clientSecret,
    )}`;

  return {
    ok:
      true,

    mode:
      PAYMOB_MODE,

    intention_id:
      result?.id ||
      null,

    order_id:
      result?.intention_order_id ||
      null,

    client_secret:
      clientSecret,

    checkout_url:
      checkoutUrl,

    special_reference:
      result?.special_reference ||
      intentionBody?.special_reference ||
      null,

    currency:
      "EGP",
  };
}

// ============================================================
// PAYMENT VERIFICATION / TRANSACTION INQUIRY
// ============================================================

async function getPaymobAuthToken() {
  if (!PAYMOB_API_KEY) {
    throw new Error(
      `Missing Paymob ${isLive ? "Live" : "Test"} API Key for payment verification.`,
    );
  }

  const response = await fetch(
    `${PAYMOB_BASE_URL}/api/auth/tokens`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        api_key: PAYMOB_API_KEY,
      }),
    },
  );

  const text = await response.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  // Paymob's transaction-inquiry authentication flow uses the
  // Dashboard API Key to obtain a short-lived auth token.
  // Keep compatibility with both the classic response shape
  // { token: "..." } and a wrapped response { body: { token: "..." } }.
  const authToken =
    data?.token ??
    data?.body?.token ??
    data?.data?.token ??
    null;

  if (!response.ok || !authToken) {
    throw new Error(`Paymob authentication failed: ${text}`);
  }

  return String(authToken);
}

// Official Paymob Transaction Inquiry API: retrieve the last
// transaction by the merchant_order_id used as special_reference.
// This is a fallback for the browser redirect when a callback is
// delayed or not supported by the selected wallet integration.
async function inquirePaymobByMerchantReference(reference: string) {
  const token = await getPaymobAuthToken();

  const response = await fetch(
    `${PAYMOB_BASE_URL}/api/ecommerce/orders/transaction_inquiry`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        auth_token: token,
        merchant_order_id: reference,
      }),
    },
  );

  const text = await response.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!response.ok || !data) {
    throw new Error(`Paymob transaction inquiry failed: ${text}`);
  }

  return data;
}

async function inquirePaymobByTransactionId(transactionId: string) {
  const token = await getPaymobAuthToken();
  const cleanId = String(transactionId || "").trim();
  if (!cleanId) throw new Error("Missing Paymob transaction ID.");

  const response = await fetch(
    `${PAYMOB_BASE_URL}/api/acceptance/transactions/${encodeURIComponent(cleanId)}`,
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );

  const text = await response.text();
  let data: any = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!response.ok || !data) {
    throw new Error(`Paymob transaction lookup failed: ${text}`);
  }

  return data;
}

async function verifyAndFinalizePayment(params: {
  reference: string;
  transactionId?: string;
  expectedType?: "order" | "prime";
}) {
  const reference = String(params.reference || "").trim();
  if (!reference) throw new Error("Missing payment reference.");

  // Prefer an explicit transaction ID when Paymob returned one.
  // Otherwise use the official merchant-order/reference inquiry.
  const transaction = params.transactionId
    ? await inquirePaymobByTransactionId(params.transactionId)
    : await inquirePaymobByMerchantReference(reference);

  const success = transaction?.success === true;
  const pending = transaction?.pending === true;
  const errorOccurred = transaction?.error_occured === true;
  const refunded =
    transaction?.is_refunded === true ||
    transaction?.is_refund === true ||
    Number(transaction?.refunded_amount_cents || 0) > 0;
  const voided =
    transaction?.is_voided === true ||
    transaction?.is_void === true;
  const currency = String(transaction?.currency || "").toUpperCase();

  if (currency && currency !== "EGP") {
    throw new Error("Paymob payment currency mismatch.");
  }

  // Do not allow a Test transaction to confirm a Live order or vice versa.
  if (
    typeof transaction?.is_live === "boolean" &&
    transaction.is_live !== isLive
  ) {
    throw new Error("Paymob payment mode mismatch.");
  }

  const resolvedReference = String(
    transaction?.merchant_order_id ||
      transaction?.order?.merchant_order_id ||
      transaction?.special_reference ||
      reference,
  ).trim();

  if (
    resolvedReference !== reference &&
    !resolvedReference.endsWith(reference)
  ) {
    throw new Error("Paymob merchant reference mismatch.");
  }

  const amountCents = Number(
    transaction?.amount_cents ??
      transaction?.amount_cents_int ??
      transaction?.original_amount ??
      0,
  );

  const integrationId = Number(transaction?.integration_id || 0);

  const isPrime =
    params.expectedType === "prime" ||
    reference.startsWith("ELORY-LIVE-") ||
    reference.startsWith("ELORY-TEST-");

  if (isPrime) {
    const prime = await findPrimeByReference(reference);
    if (!prime) throw new Error("Prime payment reference not found.");

    const validPrimeIntegrations = [
      CARD_INTEGRATION_ID,
      WALLET_INTEGRATION_ID,
    ].filter((id) => Number(id) > 0);

    if (!validPrimeIntegrations.includes(integrationId)) {
      throw new Error("Unexpected Paymob integration for Prime.");
    }

    const expectedPrimeAmount = Math.round(Number(prime.price ?? PRIME_PRICE) * 100);
    if (!Number.isSafeInteger(expectedPrimeAmount) || amountCents !== expectedPrimeAmount) {
      throw new Error("Prime payment amount does not match the saved subscription price.");
    }

    if (pending) {
      return {
        ok: true,
        confirmed: false,
        status: "pending",
        prime_id: prime.id,
        transaction_id: transaction?.id || null,
      };
    }

    if (refunded || voided || !success || errorOccurred) {
      if (String(prime.status || "") === "pending") {
        await markPrimeFailed(prime.id);
      }
      return {
        ok: true,
        confirmed: false,
        status: "payment_failed",
        prime_id: prime.id,
        transaction_id: transaction?.id || null,
      };
    }

    if (prime.active === true && prime.status === "active") {
      return {
        ok: true,
        confirmed: true,
        status: "prime_activated",
        prime_id: prime.id,
        transaction_id: transaction?.id || null,
      };
    }

    const activated = await activatePrime(prime.id, reference);
    return {
      ok: true,
      confirmed: true,
      status: "prime_activated",
      transaction_id: transaction?.id || null,
    };
  }

  const order = await findOrderById(reference);
  if (!order) throw new Error("Normal order not found.");

  const expectedAmount = Math.round(Number(order.total || 0) * 100);
  if (!Number.isSafeInteger(expectedAmount) || expectedAmount <= 0) {
    throw new Error("Invalid local order amount.");
  }
  if (amountCents !== expectedAmount) {
    throw new Error("Payment amount does not match order total.");
  }

  const expectedIntegration =
    normalizePaymentMethod(order.payment_method) === "vodafone_cash"
      ? WALLET_INTEGRATION_ID
      : CARD_INTEGRATION_ID;

  if (
    !expectedIntegration ||
    integrationId !== Number(expectedIntegration)
  ) {
    throw new Error("Unexpected Paymob integration for this order.");
  }

  if (pending) {
    return {
      ok: true,
      confirmed: false,
      status: "pending",
      order_id: order.id,
      transaction_id: transaction?.id || null,
    };
  }

  if (refunded || voided || !success || errorOccurred) {
    if (String(order.status || "") === "جاري الدفع") {
      await updateOrderPaymentStatus(order.id, "فشل الدفع");
    }
    return {
      ok: true,
      confirmed: false,
      status: "payment_failed",
      order_id: order.id,
      transaction_id: transaction?.id || null,
    };
  }

  const updated = await updateOrderPaymentStatus(order.id, "طلب جديد");
  await redeemCouponForOrder(order);
  return {
    ok: true,
    confirmed: true,
    status: "order_payment_confirmed",
    order_id: order.id,
    transaction_id: transaction?.id || null,
  };
}

// ============================================================
// MAIN
// ============================================================

serve(async (request: Request) => {
  if (
    request.method ===
    "OPTIONS"
  ) {
    return new Response(
      "ok",
      {
        headers:
          corsHeaders,
      },
    );
  }

  try {
    if (
      request.method !==
      "POST"
    ) {
      return json(
        {
          ok: false,
          error:
            "Method not allowed.",
        },
        405,
      );
    }

    const rawBody =
      await request.text();

    let body: any = {};

    try {
      body =
        rawBody
          ? JSON.parse(rawBody)
          : {};
    } catch {
      return json(
        {
          ok: false,
          error:
            "Invalid JSON body.",
        },
        400,
      );
    }

    // --------------------------------------------------------
    // PUBLIC PAYMENT CAPABILITIES (NO SECRETS)
    // --------------------------------------------------------

    if (body?.action === "payment_capabilities") {
      const methodAvailability = await getPaymentMethodAvailability();
      const cardEnabled = Number(CARD_INTEGRATION_ID) > 0 && methodAvailability.card;
      const walletEnabled = Number(WALLET_INTEGRATION_ID) > 0 && methodAvailability.wallet;
      return json({
        ok: true,
        mode: PAYMOB_MODE,
        card_enabled: cardEnabled,
        wallet_enabled: walletEnabled,
        cod_enabled: methodAvailability.cod,
        prime_enabled: cardEnabled,
      }, 200);
    }

    // --------------------------------------------------------
    // VERIFIED PAYMENT RETURN / INQUIRY
    // --------------------------------------------------------

    if (body?.action === "verify_payment") {
      try {
        const result = await verifyAndFinalizePayment({
          reference: String(body?.reference || ""),
          transactionId: body?.transaction_id
            ? String(body.transaction_id)
            : undefined,
          expectedType:
            body?.payment_type === "prime" ? "prime" : "order",
        });
        return json(result, 200);
      } catch (error) {
        console.error("ELORY PAYMENT VERIFICATION ERROR:", error);
        return json({
          ok: false,
          confirmed: false,
          error: error instanceof Error ? error.message : String(error),
        }, 400);
      }
    }

    // --------------------------------------------------------
    // PAYMOB TRANSACTION CALLBACK
    // --------------------------------------------------------

    if (
      body?.type ===
        "TRANSACTION" &&
      body?.obj
    ) {
      return await handlePaymobCallback(
        new Request(
          request.url,
          {
            method:
              "POST",

            headers:
              request.headers,

            body:
              JSON.stringify(
                body,
              ),
          },
        ),
      );
    }

    // --------------------------------------------------------
    // PRIME
    // --------------------------------------------------------

    if (
      body?.type === "prime_subscription" ||
      body?.prime_only === true
    ) {
      const authUserId = await getAuthenticatedUserId(request);
      if (!authUserId) {
        return json({ ok: false, error: "يجب تسجيل الدخول لشراء Elory Prime." }, 401);
      }
      const requestedUserId = String(body?.user_id || "").trim();
      if (requestedUserId && requestedUserId !== authUserId) {
        return json({ ok: false, error: "حساب المستخدم لا يطابق جلسة تسجيل الدخول." }, 403);
      }
      body.user_id = authUserId;

      const methodAvailability = await getPaymentMethodAvailability();
      if (!methodAvailability.card || Number(CARD_INTEGRATION_ID) <= 0) {
        return json({ ok: false, error: "الدفع بالبطاقة واشتراك Prime غير متاحين حاليًا." }, 403);
      }
      body.allow_wallet_payment = methodAvailability.wallet;

      const result =
        await createPrimeIntention(
          body,
        );

      return json(
        result,
        200,
      );
    }

    // --------------------------------------------------------
    // NORMAL ONLINE ORDER
    // --------------------------------------------------------

    const paymentMethod =
      normalizePaymentMethod(
        body?.payment_method,
      );

    if (
      paymentMethod ===
        "card" ||
      paymentMethod ===
        "vodafone_cash"
    ) {
      const authUserId = await getAuthenticatedUserId(request);
      const requestedUserId = String(body?.user_id || "").trim();
      if (requestedUserId && requestedUserId !== authUserId) {
        return json({ ok: false, error: "حساب المستخدم لا يطابق جلسة تسجيل الدخول." }, 403);
      }
      body.user_id = authUserId;

      const methodAvailability = await getPaymentMethodAvailability();
      if (paymentMethod === "card" && !methodAvailability.card) {
        return json({ ok: false, error: "الدفع بالبطاقة غير متاح حاليًا." }, 403);
      }
      if (paymentMethod === "vodafone_cash" && !methodAvailability.wallet) {
        return json({ ok: false, error: "الدفع بالمحافظ الإلكترونية غير متاح حاليًا." }, 403);
      }

      const result =
        await createNormalOrderIntention(
          body,
        );

      return json(
        result,
        200,
      );
    }

    // Cash on delivery is intentionally handled by the
    // frontend directly through Supabase and never reaches
    // Paymob.
    if (
      paymentMethod ===
      "cash_on_delivery"
    ) {
      return json(
        {
          ok: false,
          error:
            "Cash on delivery does not use Paymob.",
        },
        400,
      );
    }

    return json(
      {
        ok: false,
        error:
          "Unsupported payment type.",
        supported:
          [
            "card",
            "vodafone_cash",
            "prime_subscription",
          ],
      },
      400,
    );
  } catch (error) {
    console.error(
      "Elory Paymob error:",
      error,
    );

    return json(
      {
        ok: false,

        error:
          error instanceof Error
            ? error.message
            : String(error),

        mode:
          PAYMOB_MODE,
      },
      500,
    );
  }
});