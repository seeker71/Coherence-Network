// Hati Suci — native Android shell (Capacitor). Pure CARRIER: it loads the web
// body at /hati-suci and exposes the device sensors the bare web cannot reach,
// so the membrane's locator doors (household-membrane.form: `locate`) can sense
// presence. Nothing here holds logic — the body is Form, the UI is the web app.
//
// Build: see README.md (npm i → npx cap add android → Android Studio → APK).
import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.coherencycoin.hatisuci",
  appName: "Hati Suci",
  // `webDir` is required by the CLI even when `server.url` is set (it points the
  // bundled-asset fallback at an empty dir we never ship).
  webDir: "www",
  server: {
    // Thinnest shell: load the live web body. The page feature-detects Capacitor
    // (`Capacitor.isNativePlatform()`) and calls the device plugins when it runs
    // inside this shell; in a plain browser it uses what the web allows.
    // Swap this for a bundled web build to make the app offline-capable.
    url: "https://coherencycoin.com/hati-suci",
    cleartext: false,
  },
  plugins: {
    // by-pin (household-membrane.form: locate) — GPS → nearest-place recipe.
    Geolocation: {},
  },
};

export default config;
