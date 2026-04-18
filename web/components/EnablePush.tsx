"use client";

/**
 * EnablePush — the small warm affordance that invites a visitor to let
 * the organism speak back when the app is closed.
 *
 * Flow on tap:
 *   1. Register /sw.js as a service worker
 *   2. Fetch the VAPID public key from the API
 *   3. Call pushManager.subscribe() with that key
 *   4. POST the resulting PushSubscription to /api/push/subscribe
 *      along with the viewer's contributor_id and fingerprint
 *   5. Flip to "subscribed" state — future pushes land on her device
 *
 * Iron-cast gating: only renders when the browser actually supports
 * service workers + push. iOS requires the site be added to the home
 * screen first (PWA install), so on iOS we show a short instruction
 * instead of a broken button.
 */

import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/api";
import { useT, useLocale } from "@/components/MessagesProvider";
import { ensureFingerprint, readIdentity } from "@/lib/identity";

type State =
  | "loading"        // determining browser support + current state
  | "unsupported"    // this browser can't do web push
  | "ios-install"    // iOS Safari: must install PWA first
  | "ready"          // supported, not yet subscribed
  | "subscribing"    // in-flight
  | "subscribed"     // done
  | "denied"         // user said no to notification permission
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
        // On iOS, push only works if the site is installed to home screen
        if (isIosSafari() && !isStandalone()) {
          setState("ios-install");
          return;
        }
        const reg = await navigator.serviceWorker.register("/sw.js");
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          setState("subscribed");
          return;
        }
        if (Notification.permission === "denied") {
          setState("denied");
          return;
        }
        setState("ready");
      } catch (e) {
        setError(String(e));
        setState("error");
      }
    })();
  }, []);

  async function subscribe() {
    setState("subscribing");
    setError(null);
    try {
      const base = getApiBase();
      const keyRes = await fetch(`${base}/api/push/vapid-public-key`);
      if (!keyRes.ok) {
        throw new Error(`vapid key endpoint: ${keyRes.status}`);
      }
      const { public_key } = await keyRes.json();
      if (!public_key) throw new Error("no public key");

      const reg = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;

      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setState(permission === "denied" ? "denied" : "ready");
        return;
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
      if (!subRes.ok) {
        throw new Error(`subscribe endpoint: ${subRes.status}`);
      }
      setState("subscribed");
    } catch (e) {
      setError(String(e));
      setState("error");
    }
  }

  if (state === "loading" || state === "unsupported") return null;

  // One small container — warm, present, not insistent.
  return (
    <section
      className="max-w-3xl mx-3 sm:mx-auto mt-3 px-5 py-4 rounded-2xl border border-[hsl(var(--primary)/0.25)] bg-card"
      aria-label={t("enablePush.ariaLabel")}
    >
      <p className="text-[11px] uppercase tracking-[0.18em] font-semibold text-[hsl(var(--primary))] mb-1.5">
        {t("enablePush.eyebrow")}
      </p>
      {state === "ready" && (
        <>
          <p className="text-base font-light text-foreground leading-snug mb-3">
            {t("enablePush.heading")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed mb-3">
            {t("enablePush.lede")}
          </p>
          <button
            type="button"
            onClick={subscribe}
            className="inline-flex items-center gap-2 rounded-full bg-[hsl(var(--primary))] hover:opacity-90 text-[hsl(var(--primary-foreground))] px-4 py-2 text-sm font-medium transition-opacity"
          >
            {t("enablePush.cta")}
          </button>
        </>
      )}
      {state === "subscribing" && (
        <p className="text-sm text-muted-foreground">{t("enablePush.subscribing")}</p>
      )}
      {state === "subscribed" && (
        <p className="text-sm text-foreground">
          <span className="text-lg mr-1.5" aria-hidden="true">✓</span>
          {t("enablePush.subscribed")}
        </p>
      )}
      {state === "ios-install" && (
        <>
          <p className="text-base font-light text-foreground leading-snug mb-2">
            {t("enablePush.iosHeading")}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {t("enablePush.iosLede")}
          </p>
        </>
      )}
      {state === "denied" && (
        <p className="text-sm text-muted-foreground">{t("enablePush.denied")}</p>
      )}
      {state === "error" && (
        <p className="text-sm text-muted-foreground">
          {t("enablePush.error")}
          {error && <span className="block mt-1 text-xs opacity-60">{error}</span>}
        </p>
      )}
    </section>
  );
}
