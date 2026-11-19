const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/avif', 'video/mp4', 'video/webm']);
const PREFIX_PERMISSIONS = {
  products: new Set(['products.add', 'products.edit']),
  categories: new Set(['categories.manage']),
  site: new Set(['offers.manage', 'website.manage']),
  hero: new Set(['website.manage'])
};
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Authorization, Content-Type, X-Elory-Permission',
  'Access-Control-Max-Age': '86400'
};

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...CORS, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' }
  });
}

function decodeKey(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

function validKey(key) {
  return key.split('/').every((part) =>
    part.length > 0 && part !== '.' && part !== '..' && /^[A-Za-z0-9._-]{1,100}$/.test(part)
  );
}

async function hasPermission(request, env, permission) {
  const authorization = request.headers.get('Authorization') || '';
  if (!authorization.startsWith('Bearer ')) return false;
  const headers = { Authorization: authorization, apikey: env.SUPABASE_PUBLISHABLE_KEY };
  const userResponse = await fetch(env.SUPABASE_URL + '/auth/v1/user', { headers });
  if (!userResponse.ok) return false;
  const permissionResponse = await fetch(env.SUPABASE_URL + '/rest/v1/rpc/has_staff_permission', {
    method: 'POST',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ p_permission: permission })
  });
  if (!permissionResponse.ok) return false;
  return (await permissionResponse.text()).trim() === 'true';
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/+|\/+$/g, '');

    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: CORS });
    if (path === 'health' && request.method === 'GET') return json({ ok: true, service: 'elory-media' });

    if (path.startsWith('media/') && ['GET', 'HEAD'].includes(request.method)) {
      const key = decodeKey(path.slice('media/'.length));
      if (!key || !validKey(key)) return new Response('Not found', { status: 404, headers: CORS });
      const object = await env.MEDIA_BUCKET.get(key);
      if (!object) return new Response('Not found', { status: 404, headers: CORS });
      const headers = new Headers(CORS);
      object.writeHttpMetadata(headers);
      headers.set('ETag', object.httpEtag);
      headers.set('Cache-Control', 'public, max-age=31536000, immutable');
      headers.set('X-Content-Type-Options', 'nosniff');
      return new Response(request.method === 'HEAD' ? null : object.body, { headers });
    }

    if (path.startsWith('upload/') && request.method === 'POST') {
      const key = decodeKey(path.slice('upload/'.length));
      if (!key) return json({ error: 'invalid_upload', message: 'مسار الملف غير صالح.' }, 400);
      const parts = key.split('/');
      const permission = request.headers.get('X-Elory-Permission') || '';
      const contentType = (request.headers.get('Content-Type') || '').split(';')[0].trim().toLowerCase();
      const contentLength = Number(request.headers.get('Content-Length') || 0);
      const maxBytes = contentType.startsWith('video/') ? 50 * 1024 * 1024 : 15 * 1024 * 1024;

      if (parts.length < 2 || !PREFIX_PERMISSIONS[parts[0]] || !validKey(key) ||
          !ALLOWED_TYPES.has(contentType) || !contentLength || contentLength > maxBytes) {
        return json({ error: 'invalid_upload', message: 'الملف أو مسار التخزين غير صالح.' }, 400);
      }
      if (!PREFIX_PERMISSIONS[parts[0]].has(permission) ||
          !(await hasPermission(request, env, permission))) {
        return json({ error: 'forbidden', message: 'ليس لديك صلاحية رفع هذا النوع من الملفات.' }, 403);
      }

      await env.MEDIA_BUCKET.put(key, request.body, {
        httpMetadata: { contentType, cacheControl: 'public, max-age=31536000, immutable' }
      });
      return json({ ok: true, key, url: url.origin + '/media/' + key }, 201);
    }

    return new Response('Not found', { status: 404, headers: CORS });
  }
};
