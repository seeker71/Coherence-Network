"use client";

/**
 * EnablePush — a small affordance that frames push notifications as
 * "on by default, turn them off anytime."
 *
 * Default posture is ON, not opt-in. The reasoning:
 *   · A visitor who reaches /feed/you has already chosen their corner.
 *     The organism speaking back is part of that corner, not a separate
 *     consent mechanism.
 *   · Browsers won't let us auto-prompt for permission (anti-abuse), so
 *     the first tap still has to confirm. But everything *after* that
 *     first confirmation stays on without a single follow-up tap, until
 *     the visitor turns it off.
 *
 * State machine:
 *   loading      — determining browser support + current state
 *   unsupported  — this browser can't do web push (rendered as null)
 *   ios-install  — iOS Safari: must add to home screen first
 *   on           — permission granted + subscription on file
 *   off          — no subscription (default-deny, or toggled off)
 *   working      — in-flight transition (subscribing or unsubscribing)
 *   error        — show the error so we can debug
 *
 * Auto-on optimization: on mount, if Notification.permission is already
 * "granted" but no subscription exists locally, silently subscribe. This
 * is true "on by default" for visitors who've granted permission before
 * (even from a different page/visit) — they get a working subscription
 * with zero taps.
 */

import { useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";
import { ensureFingerprint, readIdentity } from "@/lib/identity";

type State =
  | "loading"
  | "unsupported"
  | "ios-install"
  | "on"
  | "off"
  | "working"
  | "error";

function urlB64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const b64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  const buffer = new ArrayBuffer(raw.length);
  const out = new Uint8Array(buffer);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function isIosSafari(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  const iOS = /iPad|iPhone|iPod/.test(ua);
  const webkit = /WebKit/.test(ua);
  const notChrome = !/CriOS|FxiOS/.test(ua);
  return iOS && webkit && notChrome;
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia?.("(display-mode: standalone)").matches ||
    (navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

export function EnablePush() {
  const t = useT();
  const locale = useLocale();
  const [state, setState] = useState<State>("loading");
  const [error, setError] = useState<string | null>(null);
  // Prevent the auto-subscribe pass from racing a manual click
  const autoSubAttempted = useRef(false);

  /**
   * Subscribe flow. Returns true when a subscription is on file at the
   * end (either freshly created or already there).
   *
   * If `silent`, we won't call requestPermission() — only proceed when
   * permission is already granted. This is what the auto-on path uses
   * to avoid surprising the visitor with a prompt at page load.
   */
  async function doSubscribe(opts: { silent: boolean }): Promise<boolean> {
    const base = getApiBase();
    const keyRes = await fetch(`${base}/api/push/vapid-public-key`);
    if (!keyRes.ok) throw new Error(`vapid key endpoint: ${keyRes.status}`);
    const { public_key } = await keyRes.json();
    if (!public_key) throw new Error("no public key");

    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;

    if (Notification.permission !== "granted") {
      if (opts.silent) return false;
      const permission = await Notification.requestPermission();
      if (permission !== "granted") return false;
    }

    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlB64ToUint8Array(public_key),
    });

    const { contributorId, fingerprint } = readIdentity();
    const fp = fingerprint || ensureFingerprint();

    const subRes = await fetch(`${base}/api/push/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subscription: sub.toJSON(),
        contributor_id: contributorId || undefined,
        fingerprint: fp,
        user_agent: navigator.userAgent,
        locale,
      }),
    });
    if (!subRes.ok) throw new Error(`subscribe endpoint: ${subRes.status}`);
    return true;
  }

  /**
   * Unsubscribe flow. Removes the local PushSubscription and tells the
   * server to drop the row. Idempotent — safe even if either side is
   * already cleared.
   */
  async function doUnsubscribe(): Promise<void> {
    const base = getApiBase();
    const reg = await navigator.serviceWorker.getRegistration("/sw.js");
    if (!reg) return;
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      const endpoint = existing.endpoint;
      try {
        await existing.unsubscribe();
      } catch {
        // browser-side failure shouldn't block server-side cleanup
      }
      await fetch(`${base}/api/push/unsubscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint }),
      }).catch(() => undefined);
    }
  }

  useEffect(() => {
    (async () => {
      try {
        if (typeof window === "undefined") return;
        if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
          if (isIosSafari() && !isStandalone()) {
            setState("ios-install");
          } else {
            setState("unsupported");
          }
          return;
        }
        if (isIosSafari() && !isStandalone()) {
          setState("ios-install");
          return;
        }

        const reg = await navigator.serviceWorker.register("/sw.js");
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          setState("on");
          return;
        }

        // Auto-on path: if permission is already granted, subscribe
        // silently — the visitor never has to tap.
        if (Notification.permission === "granted" && !autoSubAttempted.current) {
          autoSubAttempted.current = true;
          try {
            const ok = await doSubscribe({ silent: true });
            setState(ok ? "on" : "off");
            return;
          } catch (e) {
            // Non-fatal; fall through to render the manual toggle
            console.warn("auto-subscribe failed:", e);
          }
        }
        setState("off");
      } catch (e) {
        setError(String(e));
        setState("error");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleToggle() {
    if (state === "working") return;
    if (state === "on") {
      setState("working");
      setError(null);
      try {
        await doUnsubscribe();
        setState("off");
      } catch (e) {
        setError(String(e));
        setState("error");
      }
      return;
    }
    if (state === "off") {
      setState("working");
      setError(null);
      try {
        const ok = await doSubscribe({ silent: false });
        setState(ok ? "on" : "off");
      } catch (e) {
        setError(String(e));
        setState("error");
      }
      return;
    }
  }

  if (state === "loading" || state === "unsupported") return null;

  // The iOS install nudge stays a card — there's nothing to toggle yet.
  if (state === "ios-install") {
    return (
      <section
        className="max-w-3xl mx-3 sm:mx-auto mt-3 px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-card"
        aria-label={t("enablePush.ariaLabel")}
      >
        <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
          {t("enablePush.eyebrow")}
        </p>
        <p className="text-base font-light text-foreground leading-snug mb-2">
          {t("enablePush.iosHeading")}
        </p>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t("enablePush.iosLede")}
        </p>
      </section>
    );
  }

  const isOn = state === "on";
  const isWorking = state === "working";
  // Toggle defaults to ON visually unless we know we're off or errored.
  // (loading already returned null above.)
  const visuallyOn = isOn || isWorking;

  return (
    <section
      className="max-w-3xl mx-3 sm:mx-auto mt-3 px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-card"
      aria-label={t("enablePush.ariaLabel")}
    >
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
            {t("enablePush.eyebrow")}
          </p>
          <p className="text-base font-light text-foreground leading-snug mb-1">
            {isOn
              ? t("enablePush.onHeading")
              : t("enablePush.offHeading")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {isOn
              ? t("enablePush.onLede")
              : t("enablePush.offLede")}
          </p>
          {state === "error" && error && (
            <p className="mt-2 text-xs text-muted-foreground opacity-70">
              {t("enablePush.error")}
              <span className="block mt-1 opacity-60">{error}</span>
            </p>
          )}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={visuallyOn}
          aria-label={
            isOn ? t("enablePush.toggleOffAria") : t("enablePush.toggleOnAria")
          }
          onClick={handleToggle}
          disabled={isWorking}
          className={[
            "relative inline-flex shrink-0 items-center h-7 w-12 rounded-full transition-colors",
            visuallyOn
              ? "bg-[hsl(var(--primary))]"
              : "bg-muted border border-border",
            isWorking ? "opacity-60" : "",
          ].join(" ")}
        >
          <span
            className={[
              "inline-block h-5 w-5 rounded-full bg-white shadow transition-transform",
              visuallyOn ? "translate-x-6" : "translate-x-1",
            ].join(" ")}
            aria-hidden="true"
          />
        </button>
      </div>
    </section>
  );
}
