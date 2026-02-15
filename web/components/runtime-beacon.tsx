"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

function emitRuntime(endpoint: string, runtimeMs: number) {
  const payload = {
    source: "web",
    endpoint,
    method: "GET",
    status_code: 200,
    runtime_ms: Math.max(0.1, Number(runtimeMs.toFixed(4))),
  };
  const body = JSON.stringify(payload);
  if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
    const blob = new Blob([body], { type: "application/json" });
    navigator.sendBeacon("/api/runtime-beacon", blob);
    return;
  }
  void fetch("/api/runtime-beacon", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body,
    keepalive: true,
  });
}

export default function RuntimeBeacon() {
  const pathname = usePathname();

  useEffect(() => {
    const start = performance.now();

    const nav = performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming | undefined;
    if (nav && pathname) {
      emitRuntime(pathname, nav.duration);
    }

    return () => {
      if (!pathname) return;
      const duration = performance.now() - start;
      emitRuntime(pathname, duration);
    };
  }, [pathname]);

  return null;
}

