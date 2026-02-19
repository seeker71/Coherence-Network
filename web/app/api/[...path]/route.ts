import { NextRequest, NextResponse } from "next/server";

import { getApiBase } from "@/lib/api";

const API_URL = getApiBase();
const UPSTREAM_TIMEOUT_MS = 15000;
const HOP_BY_HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "host",
  "content-length",
]);

export const dynamic = "force-dynamic";

type RouteContext = {
  params: Promise<{
    path: string[];
  }>;
};

function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const path = pathSegments.map((segment) => encodeURIComponent(segment)).join("/");
  return `${API_URL}/api/${path}${search}`;
}

function copyRequestHeaders(request: NextRequest): Headers {
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) return;
    headers.set(key, value);
  });
  return headers;
}

function copyResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) return;
    headers.set(key, value);
  });
  headers.set("cache-control", "no-store");
  return headers;
}

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  if (!Array.isArray(path) || path.length === 0) {
    return NextResponse.json({ error: "invalid_api_path" }, { status: 400 });
  }

  const upstreamUrl = buildUpstreamUrl(path, request.nextUrl.search);
  const method = request.method.toUpperCase();
  const controller = new AbortController();
  let timeout: ReturnType<typeof setTimeout> | null = null;
  const timeoutPromise = new Promise<Response>((_, reject) => {
    timeout = setTimeout(() => {
      controller.abort(new DOMException("Request timed out", "TimeoutError"));
      reject(new Error(`Upstream request timed out after ${UPSTREAM_TIMEOUT_MS}ms`));
    }, UPSTREAM_TIMEOUT_MS);
  });

  try {
    const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
    const fetchPromise = fetch(upstreamUrl, {
      method,
      headers: copyRequestHeaders(request),
      body,
      cache: "no-store",
      redirect: "manual",
      signal: controller.signal,
    });
    const upstream = await Promise.race([fetchPromise, timeoutPromise]);

    const headers = copyResponseHeaders(upstream);
    const responseBody = method === "HEAD" ? null : await upstream.arrayBuffer();
    return new NextResponse(responseBody, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  } catch (error) {
    return NextResponse.json(
      {
        status: "error",
        code: 502,
        message: "Upstream API unavailable",
        upstream_url: upstreamUrl,
        details: String(error),
      },
      { status: 502 },
    );
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

export async function GET(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function HEAD(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function OPTIONS(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function PUT(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function PATCH(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  return proxyRequest(request, context);
}
