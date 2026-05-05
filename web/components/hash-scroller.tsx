"use client";

// Auto-scroll to a #fragment after Next.js cross-page navigation.
//
// Why this exists: when a Link points to /target#anchor, Next.js navigates
// and updates window.location.hash but does not reliably scroll the new
// page to the anchor. The browser's natural anchor scroll happens before
// hydration finishes, by which point images and SSR-rendered sections may
// not have rendered their full height yet — so even if the element exists,
// its position is wrong (often 0,0 with 0 height).
//
// Strategy: poll for the target element until it has a real layout (height
// > 0 and a non-zero offsetTop), then scroll to it. Give up after ~3s so
// we don't keep polling forever on broken pages.
//
// Mount once near the top of any long page that exposes #anchor sections.

import { useEffect } from "react";

const POLL_INTERVAL_MS = 80;
const POLL_TIMEOUT_MS = 3500;

export function HashScroller() {
  useEffect(() => {
    const hash = window.location.hash;
    if (!hash || hash.length < 2) return;
    const id = decodeURIComponent(hash.slice(1));

    let stopped = false;
    const start = performance.now();

    const tryScroll = () => {
      if (stopped) return;
      const el = document.getElementById(id);
      if (el) {
        const rect = el.getBoundingClientRect();
        // Wait until the element has been laid out — non-zero height and
        // an absolute top below the viewport's current top (i.e. document
        // is tall enough that the target sits below the hero).
        if (rect.height > 0 && el.offsetTop > 0) {
          el.scrollIntoView({ behavior: "smooth", block: "start" });
          stopped = true;
          return;
        }
      }
      if (performance.now() - start < POLL_TIMEOUT_MS) {
        setTimeout(tryScroll, POLL_INTERVAL_MS);
      }
    };

    // Defer one frame so the first paint has happened.
    requestAnimationFrame(tryScroll);

    return () => {
      stopped = true;
    };
  }, []);
  return null;
}
