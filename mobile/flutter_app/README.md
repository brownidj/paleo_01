# Paleo Mobile

Flutter mobile client scaffold for Paleo.

## Run locally

```bash
cd mobile/flutter_app
flutter pub get
flutter run \
  --dart-define=PALEO_API_BASE_URL=https://localhost \
  --dart-define=PALEO_API_VERIFY_TLS=false
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
