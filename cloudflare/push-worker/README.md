# elora-push Worker source snapshot

Retrieved read-only from the deployed Cloudflare Worker `elora-push` on 24 November 2026.

- `worker.js` and `worker1.js` are preserved as separate modules exactly as returned by Cloudflare.
- The deployed Worker uses Cloudflare secret bindings; secret values are not included in this repository.
- Observed binding names: `ELORA_PUSH_WEBHOOK_SECRET`, `FCM_PROJECT_ID`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_URL`.
- Both modules are retained because the deployed script returned both. Do not upload or redeploy this snapshot until the active entrypoint/module metadata and all bindings have been verified against the live Worker.
- This snapshot is a recovery/source-preservation measure; it does not change the running Worker.
