import { NextResponse, type NextRequest } from "next/server";

/**
 * Content Security Policy (SECURITY.md §6): scripts run only from this site and only with the
 * fresh per-request nonce Next.js stamps on its own scripts, so injected markup cannot run
 * code. The browser may talk to the API, the export service and the file store, nothing else.
 * Styles allow inline: React's style attributes cannot carry a nonce.
 */
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const EXPORT_URL = process.env.NEXT_PUBLIC_EXPORT_URL ?? "";
const isDev = process.env.NODE_ENV === "development";

const origin = (url: string) => (url ? new URL(url).origin : "");

function policy(nonce: string): string {
  // The file store's public URL (presigned uploads go straight there). Read at run time.
  const files = process.env.FILES_URL;
  if (!files) throw new Error("FILES_URL is not set: the file store's public URL (deploy/README.md)");
  const reach = ["'self'", origin(API_URL), origin(EXPORT_URL), origin(files)].filter(Boolean).join(" ");
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    `img-src 'self' data: blob: ${origin(API_URL)}`.trim(),
    "font-src 'self'",
    `connect-src ${reach}`,
    "worker-src 'self'", // pdf.js
    "object-src 'none'",
    "frame-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = policy(nonce);
  const headers = new Headers(request.headers);
  headers.set("x-nonce", nonce);
  headers.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!_next/static|_next/image|favicon.ico|icon.svg|apple-icon.png).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
