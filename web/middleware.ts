import { NextResponse, type NextRequest } from "next/server";

const SUPPORTED = new Set(["en", "de", "es", "id"]);
const COOKIE_NAME = "NEXT_LOCALE";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // one year

/**
 * Resolve the best-guess locale from the Accept-Language header.
 *
 * Honors quality weights (q=0.8 etc), picks the highest-q supported
 * language prefix. Returns null when nothing matches.
 */
function bestFromAcceptLanguage(header: string | null): string | null {
  if (!header) return null;
  const candidates = header
    .split(",")
    .map((raw) => {
      const [tag, ...params] = raw.trim().split(";");
      const qParam = params.find((p) => p.trim().startsWith("q="));
      const q = qParam ? parseFloat(qParam.split("=")[1]) || 0 : 1;
      const prefix = (tag || "").split("-")[0].toLowerCase();
      return { prefix, q };
    })
    .filter((c) => c.prefix && !Number.isNaN(c.q))
    .sort((a, b) => b.q - a.q);
  for (const c of candidates) {
    if (SUPPORTED.has(c.prefix)) return c.prefix;
  }
  return null;
}

export function middleware(req: NextRequest) {
  // Route-level redirect: /vision/visual-* ids are asset nodes (images
  // generated for a concept), served on /assets/[id] where the
  // file_path actually renders. The server-component redirect inside
  // the page was getting swallowed by something in Next 15.5's error
  // handling (the error boundary returned 200 instead of Next picking
  // up NEXT_REDIRECT), so middleware handles the classification
  // instead. Runs before any page code, so no error-boundary interference.
  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/vision/")) {
    const id = pathname.slice("/vision/".length);
    if (id.startsWith("visual-lc-") || id.startsWith("visual-")) {
      return NextResponse.redirect(new URL(`/assets/${id}`, req.url), 307);
    }
  }

  const qs = req.nextUrl.searchParams.get("lang");
  const existing = req.cookies.get(COOKIE_NAME)?.value;

  // Explicit ?lang= overrides everything and gets persisted on the cookie.
  if (qs && SUPPORTED.has(qs)) {
    if (existing === qs) return NextResponse.next();
    const res = NextResponse.next();
    res.cookies.set({
      name: COOKIE_NAME,
      value: qs,
      path: "/",
      maxAge: COOKIE_MAX_AGE,
      sameSite: "lax",
    });
    return res;
  }

  // First-visit auto-detection: no ?lang=, no existing cookie. Read the
  // browser's Accept-Language and persist the best-guess locale so the
  // rest of the session honors it. Writes the cookie even on the very
  // first request so server components rendering after the middleware
  // see the detected locale via cookies().
  if (!existing) {
    const detected = bestFromAcceptLanguage(req.headers.get("accept-language"));
    if (detected) {
      const res = NextResponse.next();
      res.cookies.set({
        name: COOKIE_NAME,
        value: detected,
        path: "/",
        maxAge: COOKIE_MAX_AGE,
        sameSite: "lax",
      });
      return res;
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!api/|_next/|_vercel|favicon|visuals|.*\\.[\\w]+$).*)",
  ],
};
