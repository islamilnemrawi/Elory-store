# Elory dashboard push notifications

The Android app now uses Firebase Cloud Messaging (FCM) for new-order alerts.

## One-time Firebase Android configuration

1. Open the Firebase project already used by the Cloudflare `elora-push` Worker.
2. Register or select an Android app whose package name is exactly `com.pinky.dashboard`.
3. Download that app's `google-services.json`.
4. In GitHub, open **pinky--dashboard → Settings → Secrets and variables → Actions → New repository secret**.
5. Create the secret `ELORY_GOOGLE_SERVICES_JSON` and paste the complete JSON file content as its value.

Do not commit `google-services.json`, Firebase service-account JSON, private keys, or other credentials to the repository. The build workflow writes the Android config only into its temporary runner, validates the package name, and removes the file after the build.

The Android config must belong to the same Firebase project as the Cloudflare Worker service account and `FCM_PROJECT_ID`. Otherwise Firebase may issue tokens that the Worker cannot send to.

## Device behavior

- After a staff member signs in, the app obtains the real FCM registration token and registers it using the authenticated Supabase RPC `register_dashboard_push_device`.
- Token refreshes are registered idempotently. The app stores only a local SHA-256 token hash for duplicate suppression, not the raw token.
- Android 13+ asks for notification permission. If permission is denied, no local notification is posted.
- New-order notifications use channel `elora_orders`, matching the existing Cloudflare Worker payload, and the phone's default notification sound.
- In the background, Android displays the FCM notification. In the foreground, the app displays the same notification locally.

## Health check

The dashboard health screen tests the real Firebase registration path. It no longer creates synthetic/test push-device rows in production. A missing Firebase config is reported as a partial check rather than a fake success.
