-- Persist staff contact and last-active metadata used by the dashboard.
-- Additive only: existing staff profiles and permissions are preserved.
ALTER TABLE public.staff_profiles
  ADD COLUMN IF NOT EXISTS phone text,
  ADD COLUMN IF NOT EXISTS last_active timestamptz;

UPDATE public.staff_profiles
   SET last_active = COALESCE(updated_at, created_at)
 WHERE last_active IS NULL;
