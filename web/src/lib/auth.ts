"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, login as apiLogin, logout as apiLogout, type User } from "./api";

/** Client auth context: resolves /auth/me on mount (refresh-token boot), gates
 * every (app) page, and exposes role-aware navigation. */

export function useAuth() {
	const router = useRouter();
	const [user, setUser] = useState<User | null>(null);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		let cancelled = false;
		(async () => {
			try {
				const me = await api<User>("/auth/me");
				if (!cancelled) setUser(me);
			} catch {
				if (!cancelled) router.replace("/login");
			} finally {
				if (!cancelled) setLoading(false);
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [router]);

	return { user, loading, setUser };
}

export async function doLogin(email: string, password: string): Promise<User> {
	const { user } = await apiLogin(email, password);
	return user;
}

export async function doLogout(): Promise<void> {
	await apiLogout();
	window.location.href = "/login";
}