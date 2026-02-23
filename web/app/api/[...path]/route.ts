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

function routePath(pathSegments: string[]): string {
  return `/${pathSegments.join("/")}`;
}

function resolveCacheControl(method: string, path: string, status: number): string {
  if (method !== "GET" && method !== "HEAD") return "no-store";
  if (status >= 400) return "no-store";
  if (path.startsWith("/runtime/change-token")) return "private, max-age=5, stale-while-revalidate=5";
  if (path.startsWith("/health")) return "private, max-age=5, stale-while-revalidate=10";
  if (path.startsWith("/runtime/events")) return "private, max-age=10, stale-while-revalidate=15";
  if (path.startsWith("/agent/tasks")) return "private, max-age=15, stale-while-revalidate=20";
  if (path.startsWith("/inventory/flow") || path.startsWith("/inventory/system-lineage")) {
    return "private, max-age=45, stale-while-revalidate=60";
  }
  if (path.startsWith("/runtime/ideas/summary") || path.startsWith("/inventory/endpoint-traceability")) {
    return "private, max-age=30, stale-while-revalidate=45";
  }
  return "private, max-age=20, stale-while-revalidate=30";
}

function copyResponseHeaders(upstream: Response, method: string, path: string): Headers {
  const headers = new Headers();
  upstream.headers.forEach((value, key) => {
    if (HOP_BY_HOP_HEADERS.has(key.toLowerCase())) return;
    headers.set(key, value);
  });
  headers.set("cache-control", resolveCacheControl(method, path, upstream.status));
  return headers;
}

async function proxyRequest(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  if (!Array.isArray(path) || path.length === 0) {
    return NextResponse.json({ error: "invalid_api_path" }, { status: 400 });
  }

  const upstreamUrl = buildUpstreamUrl(path, request.nextUrl.search);
  const proxiedPath = routePath(path);
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

    const headers = copyResponseHeaders(upstream, method, proxiedPath);
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
