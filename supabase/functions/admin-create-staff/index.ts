import "jsr:@supabase/functions-js/edge-runtime.d.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";
const SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json",
};

function reply(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: cors });
}

async function serviceRequest(path: string, init: RequestInit = {}) {
  const response = await fetch(SUPABASE_URL + "/rest/v1/" + path, {
    ...init,
    headers: {
      apikey: SERVICE_ROLE_KEY,
      Authorization: "Bearer " + SERVICE_ROLE_KEY,
      "Content-Type": "application/json",
      Prefer: "return=representation,resolution=merge-duplicates",
      ...(init.headers ?? {}),
    },
  });
  const raw = await response.text();
  let data: any = null;
  try { data = raw ? JSON.parse(raw) : null; } catch { data = raw; }
  if (!response.ok) {
    throw new Error("Supabase " + response.status + ": " +
      (typeof data === "string" ? data : JSON.stringify(data)));
  }
  return data;
}

Deno.serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (request.method !== "POST") return reply({ error: "Method not allowed" }, 405);
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !SERVICE_ROLE_KEY) {
    return reply({ error: "Server-side Supabase Auth configuration is incomplete" }, 500);
  }

  const authorization = request.headers.get("authorization") ?? "";
  if (!/^Bearer\s+\S+/i.test(authorization)) {
    return reply({ error: "يجب تسجيل الدخول بحساب المالك الرئيسي" }, 401);
  }

  try {
    const actorResponse = await fetch(SUPABASE_URL + "/auth/v1/user", {
      headers: { apikey: SUPABASE_ANON_KEY, Authorization: authorization },
    });
    if (!actorResponse.ok) return reply({ error: "جلسة الدخول غير صالحة أو منتهية" }, 401);
    const actor = await actorResponse.json();

    // Staff management is reserved for the immutable primary-owner identity.
    // Never infer this authority from the editable role label or permission JSON.
    const ownerRows = await serviceRequest(
      "owner_data_reset_settings?singleton=eq.true&select=owner_id&limit=1",
      { method: "GET" },
    ) as any[];
    const primaryOwnerId = String(ownerRows?.[0]?.owner_id ?? "");
    if (!primaryOwnerId || String(actor?.id ?? "") !== primaryOwnerId) {
      return reply({ error: "إدارة الموظفين متاحة لحساب المالك الرئيسي فقط" }, 403);
    }

    const body = await request.json().catch(() => ({}));
    const name = String(body?.name ?? "").trim();
    const email = String(body?.email ?? "").trim().toLowerCase();
    const password = String(body?.password ?? "");
    const phone = String(body?.phone ?? "").trim();
    const roleInput = String(body?.role ?? "staff").trim().toLowerCase();
    const role = roleInput === "owner" ? "owner"
      : roleInput === "admin" ? "admin"
      : roleInput === "manager" ? "manager" : "staff";
    const active = body?.active !== false;
    const permissions = body?.permissions && typeof body.permissions === "object"
      ? body.permissions : {};

    if (!name) return reply({ error: "اسم الموظف مطلوب" }, 400);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return reply({ error: "البريد الإلكتروني غير صحيح" }, 400);
    }
    if (password.length < 12 || !/[A-Za-z]/.test(password) || !/[0-9]/.test(password)) {
      return reply({ error: "كلمة المرور يجب أن تكون 12 حرفًا على الأقل وتحتوي على حرف ورقم" }, 400);
    }

    const existing = await serviceRequest(
      "staff_profiles?email=eq." + encodeURIComponent(email) + "&select=id&limit=1",
      { method: "GET" },
    ) as any[];
    if (existing?.length) {
      return reply({ error: "هذا البريد مسجل بالفعل كموظف. استخدم شاشة التعديل بدل إنشاء حساب جديد." }, 409);
    }

    const authCreate = await fetch(SUPABASE_URL + "/auth/v1/admin/users", {
      method: "POST",
      headers: {
        apikey: SERVICE_ROLE_KEY,
        Authorization: "Bearer " + SERVICE_ROLE_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        password,
        email_confirm: true,
        user_metadata: { full_name: name, name, ...(phone ? { phone } : {}) },
      }),
    });

    const authRaw = await authCreate.text();
    let authData: any = null;
    try { authData = authRaw ? JSON.parse(authRaw) : null; } catch { authData = null; }
    if (!authCreate.ok || !authData?.id) {
      const message = authData?.msg || authData?.message ||
        authData?.error_description || "تعذر إنشاء حساب الدخول";
      return reply({ error: message }, authCreate.status === 422 ? 409 : 400);
    }

    try {
      const rows = await serviceRequest("staff_profiles?on_conflict=id", {
        method: "POST",
        body: JSON.stringify([{
          id: authData.id, email, name, phone: phone || null, role, permissions, active,
          last_active: new Date().toISOString(),
        }]),
      }) as any[];

      const row = rows?.[0] ?? {};
      return reply({
        id: row.id ?? authData.id,
        email: row.email ?? email,
        name: row.name ?? name,
        role: row.role ?? role,
        permissions: row.permissions ?? permissions,
        active: row.active ?? active,
        phone: row.phone ?? phone,
        last_active: row.last_active ?? new Date().toISOString(),
      }, 201);
    } catch (error) {
      // Roll back Auth user creation if profile upsert fails.
      await fetch(SUPABASE_URL + "/auth/v1/admin/users/" + encodeURIComponent(authData.id), {
        method: "DELETE",
        headers: { apikey: SERVICE_ROLE_KEY, Authorization: "Bearer " + SERVICE_ROLE_KEY },
      }).catch(() => {});
      throw error;
    }
  } catch (error) {
    console.error("admin-create-staff:", error);
    return reply({ error: error instanceof Error ? error.message : String(error) }, 500);
  }
});
