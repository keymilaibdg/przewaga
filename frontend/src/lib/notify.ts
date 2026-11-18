// Local notifications in the Android app (no server, no push service).
//  1. Background check: @capacitor/background-runner runs public/runners/background.js every ~2 h; it downloads
//     meta.json and shows new notifications (new tip, withdrawn tip, settled tip) according to the settings.
//  2. Coupon reminders: @capacitor/local-notifications schedules a reminder one hour before each coupon match.
// In the web version every function is a no-op (the plugins are imported only inside the APK).
import type { UserSettings } from "../types/domain";
import type { CouponLeg } from "./coupon";

export const RUNNER_LABEL = "pl.przewaga.check";
const REMINDER_BASE = 1_000_000; // notification ids of coupon reminders: REMINDER_BASE + hash
const REMINDER_LEAD_MS = 60 * 60 * 1000;

export type PermissionState = "granted" | "denied" | "prompt" | "unsupported";

const native = () => typeof __NATIVE__ !== "undefined" && __NATIVE__;

async function local() {
  return (await import("@capacitor/local-notifications")).LocalNotifications;
}

async function runner() {
  return (await import("@capacitor/background-runner")).BackgroundRunner;
}

export async function notificationPermission(): Promise<PermissionState> {
  if (!native()) return "unsupported";
  try {
    const { display } = await (await local()).checkPermissions();
    return display === "granted" ? "granted" : display === "denied" ? "denied" : "prompt";
  } catch {
    return "unsupported";
  }
}

export async function requestNotificationPermission(): Promise<PermissionState> {
  if (!native()) return "unsupported";
  try {
    const { display } = await (await local()).requestPermissions();
    return display === "granted" ? "granted" : display === "denied" ? "denied" : "prompt";
  } catch {
    return "unsupported";
  }
}

/** Pass the data address and the notification settings to the background runner (it has no access to the app's storage). */
export async function configureBackgroundCheck(settings: UserSettings, dataUrl: string): Promise<void> {
  if (!native()) return;
  try {
    await (await runner()).dispatchEvent({
      label: RUNNER_LABEL,
      event: "configure",
      details: { dataUrl, notifications: settings.notifications },
    });
  } catch (e) {
    console.warn("background runner unavailable", e);
  }
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 900_000;
}

/** Replace all pending coupon reminders with one per coupon match (1 h before kick-off). Returns how many were scheduled. */
export async function scheduleCouponReminders(legs: CouponLeg[], enabled: boolean): Promise<number> {
  if (!native()) return 0;
  try {
    const ln = await local();
    const pending = await ln.getPending();
    const old = pending.notifications.filter((n) => n.id >= REMINDER_BASE && n.id < REMINDER_BASE + 900_000);
    if (old.length) await ln.cancel({ notifications: old.map((n) => ({ id: n.id })) });
    if (!enabled || (await notificationPermission()) !== "granted") return 0;
    const now = Date.now();
    const items = legs
      .map((l) => ({ l, at: Date.parse(l.kickoff) - REMINDER_LEAD_MS }))
      .filter(({ at }) => at > now + 60_000)
      .map(({ l, at }) => ({
        id: REMINDER_BASE + hash(l.eventId),
        title: "Mecz z kuponu za godzinę",
        body: `${l.eventLabel}: ${l.label} @ ${l.price.toFixed(2)} — sprawdź kurs i składy przed postawieniem.`,
        schedule: { at: new Date(at), allowWhileIdle: true },
        extra: { eventId: l.eventId },
      }));
    if (items.length) await ln.schedule({ notifications: items });
    return items.length;
  } catch (e) {
    console.warn("local notifications unavailable", e);
    return 0;
  }
}
