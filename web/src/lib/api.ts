"use client";

/** API client: access token lives in memory (module var), refresh token in
 * localStorage, and a 401 triggers exactly one refresh-and-replay before giving
 * up. Upgrade path (httpOnly cookies via a Next route-handler proxy) is
 * documented in the v2 plan — not built. */

export interface ApiErrorEnvelope {
	error: { code: string; message: string; details?: unknown };
}

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
	) {
		super(message);
	}
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8900/api/v1";
const EXPORT_URL = process.env.NEXT_PUBLIC_EXPORT_URL ?? "http://localhost:8902";
const REFRESH_KEY = "phd.refresh";

let accessToken: string | null = null;
export const setAccessToken = (token: string | null): void => {
	accessToken = token;
};

export const saveRefresh = (token: string): void => localStorage.setItem(REFRESH_KEY, token);
export const clearTokens = (): void => {
	accessToken = null;
	localStorage.removeItem(REFRESH_KEY);
};

export interface User {
	id: string;
	email: string;
	full_name: string;
	role: "scholar" | "supervisor" | "admin";
	scholar_id?: string | null;
	supervisor_id?: string | null;
}

async function tryRefresh(): Promise<boolean> {
	const refresh = localStorage.getItem(REFRESH_KEY);
	if (!refresh) return false;
	const res = await fetch(`${API_URL}/auth/refresh`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ refresh_token: refresh }),
	});
	if (!res.ok) {
		clearTokens();
		return false;
	}
	const body = (await res.json()) as { access_token: string; refresh_token: string };
	accessToken = body.access_token;
	saveRefresh(body.refresh_token);
	return true;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
	const run = () =>
		fetch(`${API_URL}${path}`, {
			...init,
			headers: {
				"Content-Type": "application/json",
				...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
				...init?.headers,
			},
		});

	let res = await run();
	if (res.status === 401 && (await tryRefresh())) {
		res = await run();
	}
	if (!res.ok) {
		const body = (await res.json().catch(() => null)) as ApiErrorEnvelope | null;
		const err = body?.error;
		throw new ApiError(res.status, err?.code ?? "http_error", err?.message ?? `Request failed (${res.status})`);
	}
	if (res.status === 204) return undefined as T;
	return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<{ user: User; access_token: string }> {
	const body = await api<{
		access_token: string;
		refresh_token: string;
		user: User;
	}>("/auth/login", {
		method: "POST",
		body: JSON.stringify({ email, password }),
	});
	accessToken = body.access_token;
	saveRefresh(body.refresh_token);
	return { user: body.user, access_token: body.access_token };
}

export async function logout(): Promise<void> {
	const refresh = localStorage.getItem(REFRESH_KEY);
	if (refresh) {
		await fetch(`${API_URL}/auth/logout`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ refresh_token: refresh }),
		}).catch(() => undefined); // revocation is best-effort; local tokens always cleared
	}
	clearTokens();
}

/** Blob download with the same 401-refresh-replay as api(). */
async function blobDownload(base: string, path: string, filename: string): Promise<void> {
	const run = () => fetch(`${base}${path}`, { headers: { Authorization: `Bearer ${accessToken}` } });
	let res = await run();
	if (res.status === 401 && (await tryRefresh())) {
		res = await run();
	}
	if (!res.ok) {
		const body = (await res.json().catch(() => null)) as ApiErrorEnvelope | null;
		throw new ApiError(res.status, body?.error.code ?? "download_failed", body?.error.message ?? "Download failed");
	}
	const blob = await res.blob();
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = filename;
	link.click();
	URL.revokeObjectURL(url);
}

/** Blob download from the export service. */
export function exportDownload(path: string, filename: string): Promise<void> {
	return blobDownload(EXPORT_URL, path, filename);
}

/** Blob download from the API (attachment bytes). */
export function apiDownload(path: string, filename: string): Promise<void> {
	return blobDownload(API_URL, path, filename);
}

/** Multipart upload through api() — browser sets the boundary, so no JSON
 * Content-Type here. Same 401-refresh-replay. */
export async function apiUpload<T>(path: string, file: File, fields: Record<string, string>): Promise<T> {
	const form = new FormData();
	for (const [key, value] of Object.entries(fields)) form.append(key, value);
	form.append("file", file);
	const run = () =>
		fetch(`${API_URL}${path}`, {
			method: "POST",
			headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
			body: form,
		});
	let res = await run();
	if (res.status === 401 && (await tryRefresh())) {
		res = await run();
	}
	if (!res.ok) {
		const body = (await res.json().catch(() => null)) as ApiErrorEnvelope | null;
		throw new ApiError(res.status, body?.error.code ?? "upload_failed", body?.error.message ?? `Upload failed (${res.status})`);
	}
	return (await res.json()) as T;
}