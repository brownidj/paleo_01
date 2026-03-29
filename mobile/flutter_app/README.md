# Paleo Mobile

Flutter mobile client scaffold for Paleo.

## Run locally

```bash
cd mobile/flutter_app
flutter pub get
flutter run --dart-define=PALEO_API_BASE_URL=https://localhost
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
