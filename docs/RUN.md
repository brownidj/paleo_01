## reset on Mac-Mini
```zsh
cd /Users/david/PycharmProjects/Paleo_01/mobile/flutter_app
flutter clean
rm -rf ios/Pods ios/Podfile.lock ios/.symlinks
rm -rf ~/Library/Developer/Xcode/DerivedData/*
flutter pub get
cd ios && pod install --repo-update && cd ..
```

## then on iPhone
Then on the iPhone:
- Delete the Paleo Mobile app manually.
- Reboot phone (quick restart helps with bad cached installs).
- Ensure Tailscale is connected.

## Get the Tailscale IPv4 address:
tailscale ip -4
(100.73.38.100 for the mac-mini)


## Paleo_01
flutter run --release -d 00008110-001E48A02187601E --dart-define=PALEO_API_BASE_URL=http://davids-mac-mini.tail850882.ts.net --dart-define=PALEO_API_FALLBACK_BASE_URL=https://localhost --dart-define=PALEO_DISABLE_AUTO_SYNC=true
