"use client";

import { useExpertMode } from "./expert-mode-context";
import { useT } from "@/components/MessagesProvider";

export function ModeSwitcher() {
  const { mode, toggle } = useExpertMode();
  const t = useT();
  const isExpert = mode === "expert";

  return (
    <button
      type="button"
      onClick={toggle}
      title={isExpert ? t("header.modeToggleTitleToNovice") : t("header.modeToggleTitleToExpert")}
      className="rounded-lg border border-border/50 px-3 py-1.5 text-xs font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 hover:border-border"
      aria-label={isExpert ? t("header.modeToggleAriaExpert") : t("header.modeToggleAriaNovice")}
    >
      {isExpert ? t("header.modeExpert") : t("header.modeNovice")}
    </button>
  );
}
