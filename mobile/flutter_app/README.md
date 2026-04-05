# Paleo Mobile

Flutter mobile client scaffold for Paleo.

## Run locally

```bash
cd mobile/flutter_app
flutter pub get
```

Start backend first (from repo root):

```bash
scripts/backend/bootstrap_local_backend.sh
curl -v http://davids-mac-mini.tail850882.ts.net/v1/health
```

Run app:

```bash
cd mobile/flutter_app
flutter run --dart-define=PALEO_API_VERIFY_TLS=false
```

Default API resolution:
- iOS/macOS: primary `http://davids-mac-mini.tail850882.ts.net`, fallback `https://localhost`
- Android emulator: primary `https://10.0.2.2`, fallback `http://davids-mac-mini.tail850882.ts.net`

Override API URL when needed:

```bash
# iOS simulator (force localhost)
flutter run --dart-define=PALEO_API_BASE_URL=https://localhost --dart-define=PALEO_API_VERIFY_TLS=false

# Android emulator
flutter run --dart-define=PALEO_API_BASE_URL=https://10.0.2.2 --dart-define=PALEO_API_VERIFY_TLS=false

# Physical device (Tailscale host with explicit localhost fallback)
flutter run --dart-define=PALEO_API_BASE_URL=http://davids-mac-mini.tail850882.ts.net --dart-define=PALEO_API_FALLBACK_BASE_URL=https://localhost --dart-define=PALEO_API_VERIFY_TLS=false
```

## Verify

```bash
cd mobile/flutter_app
flutter analyze
flutter test
```

## Notes

- Keep mobile code isolated under `mobile/flutter_app`.
- Backend and mobile API contract changes should be updated together in this repo.
- Current MVP flow:
  - Login
  - Current Trips list (`/v1/trips`)
  - Trip Detail (`/v1/trips/{id}`) with `can_view_details` gating
