-- Repair Elory coupon staff permissions.
-- Production already has first_order_only, per_customer_limit and the
-- server-side coupon validation/redemption functions. This migration only
-- corrects the coupon-table RLS policy mode and adds a percent upper bound.
-- It intentionally does not change coupon rows, orders, hero content or media.

DROP POLICY IF EXISTS "Staff coupon delete permission" ON public.coupons;
DROP POLICY IF EXISTS "Staff coupon insert permission" ON public.coupons;
DROP POLICY IF EXISTS "Staff coupon select permission" ON public.coupons;
DROP POLICY IF EXISTS "Staff coupon update permission" ON public.coupons;

CREATE POLICY "Staff coupon delete permission"
  ON public.coupons AS PERMISSIVE FOR DELETE TO authenticated
  USING (public.has_staff_permission('coupons.manage'));

CREATE POLICY "Staff coupon insert permission"
  ON public.coupons AS PERMISSIVE FOR INSERT TO authenticated
  WITH CHECK (public.has_staff_permission('coupons.manage'));

CREATE POLICY "Staff coupon select permission"
  ON public.coupons AS PERMISSIVE FOR SELECT TO authenticated
  USING (
    public.has_staff_permission('coupons.view')
    OR public.has_staff_permission('coupons.manage')
  );

CREATE POLICY "Staff coupon update permission"
  ON public.coupons AS PERMISSIVE FOR UPDATE TO authenticated
  USING (public.has_staff_permission('coupons.manage'))
  WITH CHECK (public.has_staff_permission('coupons.manage'));

DO $migration$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.coupons'::regclass
      AND conname = 'coupons_percent_discount_max_100_check'
  ) THEN
    ALTER TABLE public.coupons
      ADD CONSTRAINT coupons_percent_discount_max_100_check
      CHECK (discount_type <> 'percent' OR discount_value <= 100);
  END IF;
END;
$migration$;

NOTIFY pgrst, 'reload schema';
