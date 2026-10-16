"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";

import { doLogout, useAuth } from "@/lib/auth";
import "./app.css";

/** Auth gate + role-gated navigation. The nav hides what the API would deny
 * anyway; the server stays the enforcer (SECURITY.md). */

type UserRole = "scholar" | "supervisor" | "admin";

const NAV: Record<UserRole, { href: string; label: string }[]> = {
	scholar: [
		{ href: "/dashboard", label: "Dashboard" },
		{ href: "/reports", label: "My reports" },
		{ href: "/meetings", label: "Meetings" },
		{ href: "/milestones", label: "Milestones" },
		{ href: "/search", label: "Search" },
	],
	supervisor: [
		{ href: "/dashboard", label: "Dashboard" },
		{ href: "/reports", label: "Reports" },
		{ href: "/meetings", label: "Meetings" },
		{ href: "/scholars", label: "Scholars" },
		{ href: "/milestones", label: "Milestones" },
		{ href: "/search", label: "Search" },
	],
	admin: [
		{ href: "/dashboard", label: "Dashboard" },
		{ href: "/reports", label: "Reports" },
		{ href: "/meetings", label: "Meetings" },
		{ href: "/scholars", label: "Scholars" },
		{ href: "/supervisors", label: "Supervisors" },
		{ href: "/milestones", label: "Milestones" },
		{ href: "/search", label: "Search" },
	],
};

export default function AppLayout({ children }: { children: ReactNode }) {
	const { user, loading } = useAuth();
	const pathname = usePathname();

	if (loading || !user) {
		return <div className="shell"><main className="content"><p className="soft">Loading…</p></main></div>;
	}

	return (
		<div className="shell">
			<header className="topbar">
				<div className="topbar-inner">
					<span className="brand">PhD Tracker</span>
					<nav className="nav" aria-label="Main navigation">
						{NAV[user.role].map((item) => (
							<Link
								key={item.href}
								href={item.href}
								className={
									pathname === item.href || pathname.startsWith(`${item.href}/`) ? "active" : ""
								}
							>
								{item.label}
							</Link>
						))}
					</nav>
					<div className="who">
						<span className="soft">
							{user.full_name} · {user.role}
						</span>
						<button type="button" className="btn btn-ghost" onClick={() => void doLogout()}>
							Sign out
						</button>
					</div>
				</div>
			</header>
			<main className="content">{children}</main>
		</div>
	);
}