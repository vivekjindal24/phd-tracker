"use client";

/** Refine auth provider over the existing token plumbing in lib/api.ts:
 * access token in memory, refresh token in localStorage, one replay on 401. */

import type { AuthProvider } from "@refinedev/core";

import { api, ApiError, clearTokens, login as apiLogin, logout as apiLogout, type User } from "@/lib/api";

export const authProvider: AuthProvider = {
	login: async ({ email, password }) => {
		try {
			const { user } = await apiLogin(email, password);
			return { success: true, redirectTo: "/dashboard", user };
		} catch (err) {
			return {
				success: false,
				error: err instanceof Error ? err : new Error("Login failed"),
			};
		}
	},
	logout: async () => {
		await apiLogout();
		return { success: true, redirectTo: "/login" };
	},
	// the api() wrapper's 401-refresh-replay is the real silent boot; this is the verdict
	check: async () => {
		try {
			await api<User>("/auth/me");
			return { authenticated: true };
		} catch {
			return { authenticated: false, logout: true, redirectTo: "/login" };
		}
	},
	getIdentity: async () => {
		try {
			return await api<User>("/auth/me");
		} catch {
			return null;
		}
	},
	onError: async (error) => {
		// the fetch wrapper already refreshed once before rethrowing; a 401 here is final
		if (error instanceof ApiError && error.status === 401) {
			clearTokens();
			return { logout: true, redirectTo: "/login" };
		}
		return {};
	},
};