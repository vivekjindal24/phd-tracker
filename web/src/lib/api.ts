/**
 * API client (SECURITY.md §1, UX Flow 0).
 * - access token in memory only; refresh token in localStorage (known tradeoff, SECURITY.md §7:
 *   upgrade path = httpOnly cookie behind a Next route-handler proxy)
 * - a 401 triggers ONE refresh-and-replay; refresh tokens are single-use, so concurrent 401s
 *   share one in-flight refresh
 * - requests slower than WAKE_AFTER_MS raise the "waking up the server" signal
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
const EXPORT_URL = process.env.NEXT_PUBLIC_EXPORT_URL ?? "";
const REFRESH_KEY = "anveshan.refresh";
const WAKE_AFTER_MS = 3000;

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let pending = 0;
let wakeTimer: ReturnType<typeof setTimeout> | null = null;
const wakeListeners = new Set<(waking: boolean) => void>();

export function onWaking(listener: (waking: boolean) => void): () => void {
  wakeListeners.add(listener);
  return () => wakeListeners.delete(listener);
}

function setWaking(waking: boolean) {
  wakeListeners.forEach((l) => l(waking));
}

function readRefresh(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null; // storage blocked: the user simply logs in each visit
  }
}

function writeRefresh(token: string | null) {
  try {
    if (token) localStorage.setItem(REFRESH_KEY, token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    // storage blocked: session lasts for this tab only
  }
}

export function hasStoredSession(): boolean {
  return readRefresh() !== null;
}

async function send(
  path: string,
  init: RequestInit,
  token: string | null,
  base = API_URL && `${API_URL}/api/v1`,
): Promise<Response> {
  if (!base) throw new ApiError(0, "config_error", "The server address is not configured.");
  pending += 1;
  if (pending === 1) wakeTimer = setTimeout(() => setWaking(true), WAKE_AFTER_MS);
  try {
    const headers = new Headers(init.headers);
    // JSON for strings; a File/Blob body (bulk import) keeps the browser's content type.
    if (typeof init.body === "string") headers.set("Content-Type", "application/json");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    return await fetch(`${base}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "network_error", "We can't reach the server. Check your connection.");
  } finally {
    pending -= 1;
    if (pending === 0) {
      if (wakeTimer) clearTimeout(wakeTimer);
      setWaking(false);
    }
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const err = body?.error;
    if (err?.code) return new ApiError(res.status, err.code, err.message, err.details ?? {});
  } catch {
    // non-JSON body (proxy error page): fall through to a generic message
  }
  return new ApiError(res.status, "http_error", `The server answered ${res.status}.`);
}

type Tokens = { access_token: string; refresh_token: string };

function store(tokens: Tokens) {
  accessToken = tokens.access_token;
  writeRefresh(tokens.refresh_token);
}

async function refresh(): Promise<boolean> {
  const token = readRefresh();
  if (!token) return false;
  refreshInFlight ??= (async () => {
    const res = await send("/auth/refresh", { method: "POST", body: JSON.stringify({ refresh_token: token }) }, null);
    if (!res.ok) {
      writeRefresh(null);
      accessToken = null;
      return false;
    }
    store(await res.json());
    return true;
  })().finally(() => {
    refreshInFlight = null;
  });
  return refreshInFlight;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res = await send(path, init, accessToken);
  if (res.status === 401 && (await refresh())) {
    res = await send(path, init, accessToken);
  }
  if (!res.ok) throw await toError(res);
  return (res.status === 204 ? undefined : await res.json()) as T;
}

/** Fetches a file (export service by default, or the API — e.g. import templates) with the
 * same token and one-refresh retry, and saves it. */
export async function download(path: string, from: "export" | "api" = "export"): Promise<void> {
  const base = from === "export" ? EXPORT_URL : API_URL && `${API_URL}/api/v1`;
  let res = await send(path, {}, accessToken, base);
  if (res.status === 401 && (await refresh())) {
    res = await send(path, {}, accessToken, base);
  }
  if (!res.ok) throw await toError(res);
  const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? "export";
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Any endpoint that answers with a token pair: password login, SSO code, set-password link. */
async function obtainTokens(path: string, body: object): Promise<void> {
  const res = await send(path, { method: "POST", body: JSON.stringify(body) }, null);
  if (!res.ok) throw await toError(res);
  store(await res.json());
}

export const login = (email: string, password: string) => obtainTokens("/auth/login", { email, password });
export const exchangeSsoCode = (code: string) => obtainTokens("/auth/sso/exchange", { code });
export const setPasswordWithLink = (token: string, password: string) =>
  obtainTokens("/auth/set-password", { token, password });

/** SSO starts with a full-page navigation to the API, which redirects to the provider. */
export function ssoStartUrl(provider: string): string {
  return `${API_URL}/api/v1/auth/sso/${provider}/start`;
}

export async function logout(): Promise<void> {
  const token = readRefresh();
  accessToken = null;
  writeRefresh(null);
  if (token) {
    await send("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token: token }) }, null);
  }
}

export const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });
