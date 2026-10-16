"use client";

import {
	BookOpenCheck,
	CalendarDays,
	GraduationCap,
	LayoutDashboard,
	LogOut,
	Menu,
	Search,
	Users,
	X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

import { doLogout, useAuth } from "@/lib/auth";
import { DropdownMenu } from "@/components/overlay";
import "./app.css";

/** Auth gate + role-gated shell. The nav hides what the API would deny anyway;
 * the server stays the enforcer (SECURITY.md). */

type Role = "scholar" | "supervisor" | "admin";

const NAV: Record<Role, { group: string; items: { href: string; label: string; icon: typeof LayoutDashboard }[] }[]> = {
	scholar: [
		{
			group: "Overview",
			items: [
				{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
				{ href: "/search", label: "Search", icon: Search },
			],
		},
		{
			group: "My record",
			items: [
				{ href: "/reports", label: "Progress reports", icon: BookOpenCheck },
				{ href: "/meetings", label: "Meetings", icon: CalendarDays },
				{ href: "/milestones", label: "Milestones", icon: GraduationCap },
			],
		},
	],
	supervisor: [
		{
			group: "Overview",
			items: [
				{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
				{ href: "/search", label: "Search", icon: Search },
			],
		},
		{
			group: "Records",
			items: [
				{ href: "/reports", label: "Reports", icon: BookOpenCheck },
				{ href: "/meetings", label: "Meetings", icon: CalendarDays },
				{ href: "/milestones", label: "Milestones", icon: GraduationCap },
			],
		},
		{
			group: "Directory",
			items: [{ href: "/scholars", label: "Scholars", icon: Users }],
		},
	],
	admin: [
		{
			group: "Overview",
			items: [
				{ href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
				{ href: "/search", label: "Search", icon: Search },
			],
		},
		{
			group: "Records",
			items: [
				{ href: "/reports", label: "Reports", icon: BookOpenCheck },
				{ href: "/meetings", label: "Meetings", icon: CalendarDays },
				{ href: "/milestones", label: "Milestones", icon: GraduationCap },
			],
		},
		{
			group: "Directory",
			items: [
				{ href: "/scholars", label: "Scholars", icon: Users },
				{ href: "/supervisors", label: "Supervisors", icon: Users },
			],
		},
	],
};

const CRUMB_LABEL: Record<string, string> = {
	dashboard: "Dashboard",
	scholars: "Scholars",
	supervisors: "Supervisors",
	meetings: "Meetings",
	reports: "Progress reports",
	milestones: "Milestones",
	search: "Search",
};

export default function AppLayout({ children }: { children: ReactNode }) {
	const { user, loading } = useAuth();
	const pathname = usePathname();
	const [navOpen, setNavOpen] = useState(false);

	if (loading || !user) {
		return (
			<div className="shell">
				<main className="content">
					<p className="soft">Loading…</p>
				</main>
			</div>
		);
	}

	const crumb = CRUMB_LABEL[pathname.split("/").filter(Boolean)[0] ?? ""] ?? "";
	const initials = user.full_name
		.split(/\s+/)
		.map((part) => part[0])
		.slice(0, 2)
		.join("");

	return (
		<div className="shell">
			<aside className={`sidebar ${navOpen ? "open" : ""}`} aria-label="Sidebar">
				<div className="brand">
					<span className="brand-name">PhD Tracker</span>
					<span className="brand-sub">v2</span>
					{navOpen && (
						<button type="button" className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }} onClick={() => setNavOpen(false)} aria-label="Close navigation">
							<X size={16} aria-hidden />
						</button>
					)}
				</div>
				{NAV[user.role].map((group) => (
					<nav className="nav-group" key={group.group} aria-label={group.group}>
						<span className="nav-group-label">{group.group}</span>
						<div className="nav">
							{group.items.map((item) => {
								const Icon = item.icon;
								const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
								return (
									<Link key={item.href} href={item.href} className={active ? "active" : ""} onClick={() => setNavOpen(false)}>
										<Icon aria-hidden />
										{item.label}
									</Link>
								);
							})}
						</div>
					</nav>
				))}
			</aside>
			<div className="main-col">
				<header className="topbar">
					<div className="crumbs" aria-label="Breadcrumb">
						<button type="button" className="btn btn-ghost btn-sm nav-toggle" onClick={() => setNavOpen(true)} aria-label="Open navigation">
							<Menu size={16} aria-hidden />
						</button>
						{crumb && (
							<>
								<span className="faint">Workspace</span>
								<span className="faint" aria-hidden>/</span>
								<span className="crumb-current">{crumb}</span>
							</>
						)}
					</div>
					<div className="user-menu">
						<DropdownMenu label={<span className="user-chip"><span className="avatar">{initials}</span>{user.full_name} · {user.role}</span>}>
							<button type="button" className="menu-danger" onClick={() => void doLogout()}>
								<LogOut size={14} aria-hidden /> Sign out
							</button>
						</DropdownMenu>
					</div>
				</header>
				<main className="content">{children}</main>
			</div>
		</div>
	);
}