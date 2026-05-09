import { NextRequest, NextResponse } from "next/server";

const CONTRIBUTOR_KEY_COOKIE = "coh_contributor_key";
const CONTRIBUTOR_NAME_COOKIE = "coh_contributor_name";

function clear(response: NextResponse): NextResponse {
  for (const name of [CONTRIBUTOR_KEY_COOKIE, CONTRIBUTOR_NAME_COOKIE]) {
    response.cookies.set({
      name,
      value: "",
      httpOnly: name === CONTRIBUTOR_KEY_COOKIE,
      path: "/",
      maxAge: 0,
    });
  }
  return response;
}

export async function POST(): Promise<NextResponse> {
  return clear(NextResponse.json({ ok: true }));
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  return clear(NextResponse.redirect(new URL("/", request.nextUrl.origin), 303));
}
