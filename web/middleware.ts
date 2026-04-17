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
