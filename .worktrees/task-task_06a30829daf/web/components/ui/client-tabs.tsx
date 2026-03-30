"use client";

import { useState } from "react";

export type TabDef = {
  id: string;
  label: string;
  /** Short badge count — shown as a small pill on the tab */
  count?: number;
};

interface ClientTabsProps {
  tabs: TabDef[];
  defaultTab?: string;
  children: (activeTab: string) => React.ReactNode;
  className?: string;
}

export function ClientTabs({ tabs, defaultTab, children, className }: ClientTabsProps) {
  const [active, setActive] = useState(defaultTab ?? tabs[0]?.id ?? "");

  return (
    <div className={className}>
      {/* Tab bar */}
      <div
        className="flex overflow-x-auto border-b border-border/40 gap-0 scrollbar-none"
        role="tablist"
        aria-label="Content sections"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`tabpanel-${tab.id}`}
            id={`tab-${tab.id}`}
            type="button"
            onClick={() => setActive(tab.id)}
            className={[
              "flex shrink-0 items-center gap-1.5 whitespace-nowrap px-4 py-2.5 text-sm font-medium transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-inset",
              "border-b-2 -mb-px",
              active === tab.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border",
            ].join(" ")}
          >
            {tab.label}
            {tab.count !== undefined && tab.count > 0 && (
              <span className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-muted/60 px-1 text-[10px] font-medium text-muted-foreground">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Panel */}
      <div
        id={`tabpanel-${active}`}
        role="tabpanel"
        aria-labelledby={`tab-${active}`}
        className="pt-6"
      >
        {children(active)}
      </div>
    </div>
  );
}
