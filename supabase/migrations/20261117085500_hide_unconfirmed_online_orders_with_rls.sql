-- Enforce unpaid-order invisibility at the table boundary as well as in the new dashboard UI.
-- This protects older installed dashboard builds that still select public.orders directly.
DROP POLICY IF EXISTS elory_hide_unconfirmed_online_orders ON public.orders;
CREATE POLICY elory_hide_unconfirmed_online_orders
ON public.orders
AS RESTRICTIVE
FOR SELECT
TO authenticated
USING (
  lower(btrim(coalesce(status, ''))) NOT IN (
    'جاري الدفع',
    'فشل الدفع',
    'فشل إنشاء الدفع',
    'payment pending',
    'pending payment',
    'payment failed',
    'failed payment',
    'failed to create payment'
  )
  AND NOT (
    lower(btrim(coalesce(payment_method, ''))) IN (
      'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
    )
    AND lower(btrim(coalesce(status, ''))) IN (
      'جديد', 'جاري التأكيد', 'pending', 'new'
    )
  )
);
