"use client";

import { useExpertMode } from "./expert-mode-context";

export function ModeSwitcher() {
  const { mode, toggle } = useExpertMode();

  return (
    <button
      type="button"
      onClick={toggle}
      title={mode === "expert" ? "Switch to simplified view" : "Switch to expert view with IDs and raw data"}
      className="rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 hover:border-border"
      aria-label={`Current mode: ${mode}. Click to toggle.`}
    >
      {mode === "expert" ? "Expert" : "Simple"}
    </button>
  );
}
