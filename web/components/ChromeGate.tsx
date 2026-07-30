// ChromeGate — hides the site-wide chrome (header, bottom nav, badge) on
// self-contained app surfaces so members/staff can't accidentally wander out
// of the app into the rest of the site with no way back. The app's own header
// lives inside the page; identity is localStorage, so it carries across
// regardless of chrome. Backend is shared; only the surface is sealed.
//
// A visit to /grocery is contained by its path. A visit to app.hati.earth is
// contained by its host, and the middleware's rewrite keeps the browser's
// pathname at "/" — so the layout reads that case from the request header and
// passes it in.
"use client";

import { usePathname } from "next/navigation";

import { isContainedPath } from "@/lib/contained-surface";

export default function ChromeGate({
  contained: containedByHost = false,
  children,
}: {
  contained?: boolean;
  children: React.ReactNode;
}) {
  const pathname = usePathname() || "";
  if (containedByHost || isContainedPath(pathname)) return null;
  return <>{children}</>;
}
