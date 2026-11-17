// Build-time constants (vite.config.ts `define` / scripts/build-offline.mjs).
/** Base URL of the published analysis JSON (web: "data"; APK: raw.githubusercontent.com/<repo>/data). */
declare const __DATA_URL__: string;
/** True inside the Android (Capacitor) build. */
declare const __NATIVE__: boolean;
declare const __APP_VERSION__: string;
/** "owner/repo" for update checks; empty when unknown. */
declare const __REPO__: string;
