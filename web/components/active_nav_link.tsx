"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function ActiveNavLink({
  href,
  label,
  isHeartbeat,
}: {
  href: string;
  label: string;
  isHeartbeat?: boolean;
}) {
  const pathname = usePathname();
  const isActive = pathname === href || pathname.startsWith(href + "/");

  if (isHeartbeat) {
    return (
      <Link
        href={href}
        className={`rounded-lg px-3 py-1.5 hover:text-primary hover:bg-accent/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 flex items-center gap-1.5 ${
          isActive ? "text-primary font-medium" : "text-primary/80"
        }`}
      >
        <span className="relative flex h-1.5 w-1.5" aria-hidden="true">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/40" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-primary/80" />
        </span>
        {label}
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className={`rounded-lg px-3 py-1.5 hover:text-foreground hover:bg-accent/60 transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1 ${
        isActive ? "text-primary font-medium" : "text-muted-foreground"
      }`}
    >
      {label}
    </Link>
  );
}
