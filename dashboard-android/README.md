# Elory Android Dashboard

This directory preserves the Android dashboard archive, overlay scripts, patch assets, database migrations, Supabase function sources, and original workflow definitions from the standalone `pinky--dashboard` repository.

## Build in this consolidated repository

The active GitHub Actions entry point is `.github/workflows/build-elory-dashboard.yml` at the repository root. It runs the preserved dashboard build pipeline from the root checkout while reading the dashboard archive and scripts from this directory.

The original workflow files remain under `dashboard-android/.github/workflows/` as source/reference copies. GitHub Actions discovers workflows only from the root `.github/workflows/` directory.

## Separation and safety

- Dashboard-specific SQL remains under `dashboard-android/supabase/` and `dashboard-android/database/`; it is not mixed into the storefront's `supabase/migrations/`.
- Storefront deployment workflows and storefront source files are not changed by this consolidation.
- No Supabase or Cloudflare resources are modified by copying these files.
- The standalone source repository remains unchanged.
