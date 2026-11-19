-- Preserve customer stock availability without exposing exact inventory or nested staff-only fields.
-- Keep staff product reads complete only for the permissions they explicitly hold.

BEGIN;

DO $preflight$
BEGIN
  IF to_regclass('public.products') IS NULL
     OR to_regclass('public.catalog_products') IS NULL
     OR to_regclass('private.elory_admin_list_products_impl(integer,integer)') IS NULL THEN
    RAISE EXCEPTION 'Catalog privacy migration stopped: expected product objects are missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_class
     WHERE oid = 'public.catalog_products'::regclass
       AND reloptions @> ARRAY['security_invoker=true']
  ) THEN
    RAISE EXCEPTION 'Catalog privacy migration stopped: catalog_products must remain SECURITY INVOKER';
  END IF;
END;
$preflight$;

-- A JSONB variants column can contain stock, SKU, codes and wholesale prices.
-- Never expose that raw payload to public/customer table reads.
REVOKE SELECT (variants) ON TABLE public.products FROM anon, authenticated;

CREATE OR REPLACE FUNCTION private.elory_public_product_metadata(p_product_id uuid)
RETURNS TABLE(in_stock boolean, variants jsonb)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
  SELECT
    CASE WHEN p.stock IS NULL THEN NULL ELSE p.stock > 0 END AS in_stock,
    CASE
      WHEN jsonb_typeof(p.variants) = 'array' THEN
        coalesce((
          SELECT jsonb_agg(
            CASE
              WHEN jsonb_typeof(v.value) = 'object' THEN
                (v.value - ARRAY[
                  'stock', 'sku', 'code', 'product_code', 'productCode',
                  'wholesale_price', 'wholesalePrice', 'internal_code',
                  'internalCode', 'barcode', 'cost_price', 'costPrice'
                ]::text[])
                ||
                CASE
                  WHEN nullif(v.value->>'stock', '') IS NOT NULL
                   AND (v.value->>'stock') ~ '^[+-]?[0-9]+([.][0-9]+)?$'
                  THEN jsonb_build_object('in_stock', (v.value->>'stock')::numeric > 0)
                  ELSE '{}'::jsonb
                END
              ELSE v.value
            END
            ORDER BY v.ordinality
          )
          FROM jsonb_array_elements(p.variants) WITH ORDINALITY AS v(value, ordinality)
        ), '[]'::jsonb)
      ELSE coalesce(p.variants, '[]'::jsonb)
    END AS variants
  FROM public.products AS p
  WHERE p.id = p_product_id
    AND coalesce(p.active, true) IS TRUE;
$function$;

REVOKE ALL ON FUNCTION private.elory_public_product_metadata(uuid)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA private TO anon, authenticated;
GRANT EXECUTE ON FUNCTION private.elory_public_product_metadata(uuid)
  TO anon, authenticated;

-- The SECURITY INVOKER view keeps normal RLS and public-column checks.
-- Only the narrow SECURITY DEFINER helper can read inventory to return booleans.
CREATE OR REPLACE VIEW public.catalog_products
WITH (security_invoker = true)
AS
SELECT
  p.id,
  p.name,
  p.description,
  p.image,
  p.category,
  p.price,
  p.old_price,
  p.discount,
  p.featured,
  p.active,
  p.colors,
  p.color_options,
  p.sizes,
  metadata.variants,
  p.gallery,
  p.created_at,
  metadata.in_stock
FROM public.products AS p
CROSS JOIN LATERAL private.elory_public_product_metadata(p.id) AS metadata
WHERE coalesce(p.active, true) IS TRUE;

-- Keep the existing staff RPC, but filter sensitive keys inside variants too.
CREATE OR REPLACE FUNCTION private.elory_admin_list_products_impl(
  p_limit integer,
  p_offset integer
)
RETURNS SETOF jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog
AS $function$
DECLARE
  v_limit integer := GREATEST(1, LEAST(COALESCE(p_limit, 500), 1000));
  v_offset integer := GREATEST(0, LEAST(COALESCE(p_offset, 0), 100000000));
  v_hidden_fields text[] := ARRAY[]::text[];
  v_hidden_variant_fields text[] := ARRAY[]::text[];
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'يجب تسجيل الدخول لعرض بيانات المنتجات'
      USING ERRCODE = '42501';
  END IF;

  IF NOT public.has_staff_permission('products.view'::text) THEN
    RAISE EXCEPTION 'ليس لديك صلاحية عرض المنتجات'
      USING ERRCODE = '42501';
  END IF;

  IF NOT public.has_staff_permission('products.wholesale_prices'::text) THEN
    v_hidden_fields := v_hidden_fields || ARRAY['wholesale_price'];
    v_hidden_variant_fields := v_hidden_variant_fields || ARRAY[
      'wholesale_price', 'wholesalePrice', 'cost_price', 'costPrice'
    ];
  END IF;

  IF NOT public.has_staff_permission('products.internal_codes'::text) THEN
    v_hidden_fields := v_hidden_fields || ARRAY['code', 'sku'];
    v_hidden_variant_fields := v_hidden_variant_fields || ARRAY[
      'sku', 'code', 'product_code', 'productCode', 'internal_code',
      'internalCode', 'barcode'
    ];
  END IF;

  RETURN QUERY
    SELECT
      CASE
        WHEN jsonb_typeof(p.variants) = 'array' THEN
          jsonb_set(
            to_jsonb(p) - v_hidden_fields,
            '{variants}',
            coalesce((
              SELECT jsonb_agg(
                CASE
                  WHEN jsonb_typeof(v.value) = 'object'
                    THEN v.value - v_hidden_variant_fields
                  ELSE v.value
                END
                ORDER BY v.ordinality
              )
              FROM jsonb_array_elements(p.variants)
                   WITH ORDINALITY AS v(value, ordinality)
            ), '[]'::jsonb),
            true
          )
        ELSE to_jsonb(p) - v_hidden_fields
      END
    FROM public.products AS p
    ORDER BY p.id ASC
    LIMIT v_limit
    OFFSET v_offset;
END;
$function$;

NOTIFY pgrst, 'reload schema';

COMMIT;
