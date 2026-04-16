import { NextResponse, type NextRequest } from "next/server";

const SUPPORTED = new Set(["en", "de", "es", "id"]);
const COOKIE_NAME = "NEXT_LOCALE";
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365; // one year

export function middleware(req: NextRequest) {
  const qs = req.nextUrl.searchParams.get("lang");
  if (!qs || !SUPPORTED.has(qs)) return NextResponse.next();

  const existing = req.cookies.get(COOKIE_NAME)?.value;
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

export const config = {
  matcher: [
    "/((?!api/|_next/|_vercel|favicon|visuals|.*\\.[\\w]+$).*)",
  ],
};
