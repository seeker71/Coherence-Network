"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const BOTTOM_NAV = [
  { href: "/vision", label: "Vision", icon: "✨" },
  { href: "/ideas", label: "Ideas", icon: "💡" },
  { href: "/contribute", label: "Contribute", icon: "🤝" },
  { href: "/resonance", label: "Resonance", icon: "🔮" },
  { href: "/pipeline", label: "Pipeline", icon: "⚡" },
];

export function MobileBottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 md:hidden border-t border-border/40 bg-background/95 backdrop-blur-md safe-area-bottom"
      aria-label="Mobile navigation"
    >
      <div className="flex h-16 items-center justify-around px-2">
        {BOTTOM_NAV.map((item) => {
          const isActive = pathname === item.href || pathname?.startsWith(item.href + "/");
          return (
            <Link
              key={item.href}
              href={item.href}
              className={[
                "flex flex-col items-center justify-center gap-0.5 rounded-xl px-3 py-2 text-xs transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-ring",
                isActive
                  ? "text-primary font-medium"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
              aria-current={isActive ? "page" : undefined}
            >
              <span className="text-base leading-none" aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
