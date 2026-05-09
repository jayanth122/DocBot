import { NextRequest, NextResponse } from "next/server";

const UPSTREAM_TIMEOUT_MS = 45000;

function getBackendBaseUrl() {
  const configured =
    process.env.BACKEND_API_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim();

  if (configured) {
    return configured.replace(/\/$/, "");
  }

  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:5001";
  }

  return "";
}

async function forward(request: NextRequest, path: string[]) {
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) {
    return NextResponse.json(
      {
        error: "Backend service is not configured.",
        message:
          "Set BACKEND_API_URL in your deployment environment to your backend endpoint.",
      },
      { status: 503 }
    );
  }

  const query = request.nextUrl.search;
  const targetUrl = `${baseUrl}/${path.join("/")}${query}`;

  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("content-length");

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    redirect: "follow",
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);
  init.signal = controller.signal;

  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const response = await fetch(targetUrl, init);
    const responseHeaders = new Headers(response.headers);
    responseHeaders.set("cache-control", "no-store");

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch (err) {
    const isAbort = err instanceof DOMException && err.name === "AbortError";

    if (isAbort) {
      return NextResponse.json(
        {
          error: "Backend timeout",
          message: "The backend took too long to respond. Please try again.",
        },
        { status: 504 }
      );
    }

    return NextResponse.json(
      {
        error: "Backend unavailable",
        message: "The backend is currently unavailable. Please try again shortly.",
      },
      { status: 503 }
    );
  } finally {
    clearTimeout(timeout);
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params;
  return forward(request, params.path || []);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params;
  return forward(request, params.path || []);
}

export async function PUT(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params;
  return forward(request, params.path || []);
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params;
  return forward(request, params.path || []);
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const params = await context.params;
  return forward(request, params.path || []);
}
