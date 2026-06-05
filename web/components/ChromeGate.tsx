// ChromeGate — hides the site-wide chrome (header, bottom nav, badge) on
// self-contained app surfaces so members/staff can't accidentally wander out
// of the Hati Suci app into the rest of the site with no way back. The app's
// own header lives inside the page; identity is localStorage, so it carries
// across regardless of chrome. Backend is shared; only the surface is sealed.
"use client";

import { usePathname } from "next/navigation";

// Routes that render as their own contained app (no marketing-site chrome).
const CONTAINED_PREFIXES = ["/hati-suci"];

export default function ChromeGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "";
  const contained = CONTAINED_PREFIXES.some(
    (p) => pathname === p || pathname.startsWith(p + "/"),
  );
  if (contained) return null;
  return <>{children}</>;
}
