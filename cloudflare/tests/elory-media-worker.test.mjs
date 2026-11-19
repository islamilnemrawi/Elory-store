import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const source = await readFile(new URL("../elory-media-worker.js", import.meta.url), "utf8");
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const { default: worker } = await import(moduleUrl);

let grantedPermission = "products.add";
const permissionCalls = [];
const writes = [];
const originalFetch = globalThis.fetch;

globalThis.fetch = async (input, init = {}) => {
  const url = String(input);
  if (url.endsWith("/auth/v1/user")) {
    return new Response(JSON.stringify({ id: "fixture-staff" }), { status: 200 });
  }
  if (url.endsWith("/rest/v1/rpc/has_staff_permission")) {
    const permission = JSON.parse(init.body || "{}").p_permission;
    permissionCalls.push(permission);
    return new Response(String(permission === grantedPermission), { status: 200 });
  }
  throw new Error(`Unexpected fetch in Worker test: ${url}`);
};

const bucket = {
  async get(key) {
    if (key !== "products/fixture.webp") return null;
    return {
      body: new Blob(["image"]).stream(),
      httpEtag: '"fixture-etag"',
      writeHttpMetadata(headers) {
        headers.set("Content-Type", "image/webp");
      }
    };
  },
  async put(key, body, options) {
    let bytes = 0;
    if (body) {
      const reader = body.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        bytes += value.byteLength;
      }
    }
    writes.push({ key, bytes, options });
  }
};

const env = {
  MEDIA_BUCKET: bucket,
  SUPABASE_URL: "https://supabase.fixture",
  SUPABASE_PUBLISHABLE_KEY: "fixture-public-key"
};

async function call(path, init = {}) {
  return worker.fetch(new Request(`https://media.fixture${path}`, init), env);
}

const health = await call("/health");
assert.equal(health.status, 200);
assert.deepEqual(await health.json(), { ok: true, service: "elory-media" });

const image = await call("/media/products/fixture.webp");
assert.equal(image.status, 200);
assert.equal(image.headers.get("Content-Type"), "image/webp");
assert.equal(image.headers.get("X-Content-Type-Options"), "nosniff");
assert.equal(image.headers.get("Cache-Control"), "public, max-age=31536000, immutable");

const missingImage = await call("/media/products/missing.webp");
assert.equal(missingImage.status, 404);

const malformedMediaPath = await call("/media/products/%E0%A4%A");
assert.equal(malformedMediaPath.status, 404);

const preflight = await call("/upload/products/new.webp", { method: "OPTIONS" });
assert.equal(preflight.status, 204);

const noAuth = await call("/upload/products/new.webp", {
  method: "POST",
  headers: { "Content-Type": "image/webp", "Content-Length": "4", "X-Elory-Permission": "products.add" },
  body: "data"
});
assert.equal(noAuth.status, 403);
assert.equal(writes.length, 0);

async function upload(path, permission, granted, expectedStatus = 201) {
  grantedPermission = granted;
  const response = await call(`/upload/${path}`, {
    method: "POST",
    headers: {
      Authorization: "Bearer fixture-session",
      "Content-Type": "image/webp",
      "Content-Length": "4",
      "X-Elory-Permission": permission
    },
    body: "data"
  });
  assert.equal(response.status, expectedStatus, `${path} with ${permission}`);
  return response;
}

// Each media prefix must enforce only its corresponding dashboard permission.
await upload("products/new.webp", "website.manage", "website.manage", 403);
await upload("products/new.webp", "products.add", "products.add");
await upload("products/edit.webp", "products.edit", "products.edit");
await upload("categories/new.webp", "categories.manage", "categories.manage");
await upload("site/new.webp", "offers.manage", "offers.manage");
await upload("site/new-cms.webp", "website.manage", "website.manage");
await upload("hero/new.webp", "offers.manage", "offers.manage", 403);
await upload("hero/new.webp", "website.manage", "website.manage");

// Bad content types and paths are rejected before a permission lookup or R2 write.
const badType = await call("/upload/products/bad.gif", {
  method: "POST",
  headers: {
    Authorization: "Bearer fixture-session",
    "Content-Type": "image/gif",
    "Content-Length": "4",
    "X-Elory-Permission": "products.add"
  },
  body: "data"
});
assert.equal(badType.status, 400);

const badPrefix = await call("/upload/private/new.webp", {
  method: "POST",
  headers: {
    Authorization: "Bearer fixture-session",
    "Content-Type": "image/webp",
    "Content-Length": "4",
    "X-Elory-Permission": "products.add"
  },
  body: "data"
});
assert.equal(badPrefix.status, 400);

assert.equal(writes.length, 6, "Only six correctly scoped uploads should reach R2");
assert.deepEqual(writes.map(x => x.key), [
  "products/new.webp",
  "products/edit.webp",
  "categories/new.webp",
  "site/new.webp",
  "site/new-cms.webp",
  "hero/new.webp"
]);
assert.ok(writes.every(x => x.bytes === 4));
assert.ok(writes.every(x => x.options.httpMetadata.contentType === "image/webp"));
assert.ok(permissionCalls.includes("products.add"));
assert.ok(permissionCalls.includes("products.edit"));
assert.ok(permissionCalls.includes("categories.manage"));
assert.ok(permissionCalls.includes("offers.manage"));
assert.ok(permissionCalls.includes("website.manage"));

globalThis.fetch = originalFetch;
console.log("PASS: Elory media Worker health, public reads, authentication, prefix permissions, and R2 upload routing.");
