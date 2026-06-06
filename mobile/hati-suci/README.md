# Hati Suci — native Android shell

A thin native Android carrier around the Hati Suci web membrane. It exists for
**one reason**: device sensors the bare web cannot reach. The body stays Form
(kernel recipes), the UI stays the web app at `/hati-suci`; this shell only loads
that page and hands it the device's senses.

## Why native (which doors it opens)

Maps to `household-membrane.form` → `(place (locate ...))`. The web alone gives
`by-pin`, `by-scan`, `by-tap`; the native shell adds the rest:

| Door | Sensor | Plugin |
|------|--------|--------|
| `by-pin` | GPS coordinates → `nearest-place` recipe | `@capacitor/geolocation` |
| `by-ssid` | **live WiFi name** (the door the bare web lacks) | `@capacitor-community/wifi` *or* `wifiwizard2` |
| `by-tap` | NFC tag at the place | `@capacitor-community/nfc` |
| `by-sense` | BLE beacons / proximity | `@capacitor-community/bluetooth-le` |
| `by-scan` | camera (QR = the join codec re-aimed) | already works in the web |

The page feature-detects the shell with `Capacitor.isNativePlatform()` and calls
a plugin only when running inside it; in a plain browser it falls back to what
the web allows. One body, two carriers.

## Build (needs the Android SDK — not buildable in CI without it)

```bash
cd mobile/hati-suci
npm install
npx cap add android          # generates the native android/ project
npx cap sync android
npx cap open android         # Android Studio → Run / Build → APK
```

`capacitor.config.ts` points `server.url` at the live web app, so the shell
needs no web build. To go offline-capable, build the web app to `www/` and drop
`server.url`.

## AndroidManifest permissions (added per door you enable)

```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>   <!-- by-pin, and Android gates SSID reads behind location -->
<uses-permission android:name="android.permission.ACCESS_WIFI_STATE"/>      <!-- by-ssid -->
<uses-permission android:name="android.permission.NFC"/>                    <!-- by-tap -->
<uses-permission android:name="android.permission.BLUETOOTH_SCAN"/>         <!-- by-sense -->
<uses-permission android:name="android.permission.CAMERA"/>                 <!-- by-scan -->
```

## Sovereignty (non-negotiable)

Location is tender. The membrane's frame holds here too: **consent-first, coarse
by default, revocable always, the sensing visible to the sensed.** Every door
asks before it senses; `by-scan` is gentlest because the consent *is* the act of
scanning. No background tracking ships without the cell choosing it.
