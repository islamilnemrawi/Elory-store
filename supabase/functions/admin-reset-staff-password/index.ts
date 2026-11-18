import { serve } from "https://deno.land/std@0.224.0/http/server.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") || "";
const SUPABASE_ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") || "";
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") || "";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-client-info",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Content-Type": "application/json; charset=utf-8",
};

function json(body: Record<string, unknown>, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: corsHeaders });
}

function isStrongPassword(value: string) {
  return value.length >= 12 && /[A-Za-z\u0600-\u06FF]/.test(value) && /\d/.test(value);
}

async function serviceGet(path: string) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    headers: {
      apikey: SUPABASE_SERVICE_ROLE_KEY,
      Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
      Accept: "application/json",
    },
  });
  if (!response.ok) throw new Error(`Supabase lookup failed (${response.status})`);
  return await response.json();
}

serve(async (request: Request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ success: false, message: "Method not allowed" }, 405);

  if (!SUPABASE_URL || !SUPABASE_ANON_KEY || !SUPABASE_SERVICE_ROLE_KEY) {
    return json({ success: false, message: "Server configuration is incomplete" }, 500);
  }

  const authorization = request.headers.get("Authorization") || "";
  if (!authorization.startsWith("Bearer ")) {
    return json({ success: false, message: "يلزم تسجيل الدخول بحساب المالك الأساسي" }, 401);
  }

  try {
    // Validate the caller JWT against Supabase Auth; never trust a caller-supplied owner ID.
    const callerResponse = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
      headers: { apikey: SUPABASE_ANON_KEY, Authorization: authorization },
    });
    if (!callerResponse.ok) return json({ success: false, message: "جلسة الدخول غير صالحة" }, 401);
    const caller = await callerResponse.json();
    const callerId = String(caller?.id || "");

    const ownerRows = await serviceGet("owner_data_reset_settings?singleton=eq.true&select=owner_id&limit=1");
    const primaryOwnerId = String(ownerRows?.[0]?.owner_id || "");
    if (!primaryOwnerId || callerId !== primaryOwnerId) {
      return json({ success: false, message: "إعادة تعيين كلمات مرور الموظفين متاحة للمالك الأساسي فقط" }, 403);
    }

    const body = await request.json().catch(() => ({}));
    const staffId = String(body?.staff_id || "").trim();
    const newPassword = String(body?.new_password || "");
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(staffId)) {
      return json({ success: false, message: "معرّف الموظف غير صحيح" }, 400);
    }
    if (!isStrongPassword(newPassword)) {
      return json({ success: false, message: "كلمة المرور يجب أن تكون 12 حرفًا على الأقل وتحتوي على حرف ورقم" }, 400);
    }
    if (staffId === primaryOwnerId) {
      return json({ success: false, message: "لا يمكن إعادة تعيين كلمة مرور حساب المالك الأساسي من هذه الشاشة" }, 403);
    }

    const profiles = await serviceGet(
      `staff_profiles?id=eq.${encodeURIComponent(staffId)}&select=id,role&limit=1`,
    );
    const target = profiles?.[0];
    if (!target) return json({ success: false, message: "حساب الموظف غير موجود" }, 404);
    if (String(target.role || "").toLowerCase() === "owner") {
      return json({ success: false, message: "إعادة تعيين كلمة مرور حساب المالك غير متاحة من إدارة الموظفين" }, 403);
    }

    const updateResponse = await fetch(
      `${SUPABASE_URL}/auth/v1/admin/users/${encodeURIComponent(staffId)}`,
      {
        method: "PUT",
        headers: {
          apikey: SUPABASE_SERVICE_ROLE_KEY,
          Authorization: `Bearer ${SUPABASE_SERVICE_ROLE_KEY}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password: newPassword }),
      },
    );
    if (!updateResponse.ok) {
      const detail = await updateResponse.text().catch(() => "");
      console.error("Auth password reset failed", updateResponse.status, detail.slice(0, 240));
      return json({ success: false, message: "تعذر تحديث كلمة مرور الموظف في Supabase Auth" }, 502);
    }

    console.info("Staff password reset completed by primary owner", { actor_id: callerId, staff_id: staffId });
    return json({ success: true, message: "تمت إعادة تعيين كلمة مرور الموظف بنجاح" });
  } catch (error) {
    console.error("admin-reset-staff-password failed", error);
    return json({ success: false, message: "حدث خطأ أثناء إعادة تعيين كلمة المرور" }, 500);
  }
});
