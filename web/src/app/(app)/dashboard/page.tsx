"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ErrorText, PageHeader } from "@/lib/ui";

interface Page<T> {
	items: T[];
	total: number;
}

export default function DashboardPage() {
	const { user } = useAuth();
	const [counts, setCounts] = useState<{ label: string; num: number; href: string }[]>([]);
	const [error, setError] = useState("");

	useEffect(() => {
		if (!user) return;
		let cancelled = false;
		(async () => {
			try {
				if (user.role === "scholar") {
					const reports = await api<Page<never>>("/reports?per_page=1");
					const meetings = await api<Page<never>>("/meetings?per_page=1");
					const milestones = await api<Page<never>>("/milestones?per_page=1");
					if (!cancelled)
						setCounts([
							{ label: "My progress reports", num: reports.total, href: "/reports" },
							{ label: "Meeting records", num: meetings.total, href: "/meetings" },
							{ label: "Milestones", num: milestones.total, href: "/milestones" },
						]);
				} else if (user.role === "supervisor") {
					const pending = await api<Page<never>>("/reports?state=submitted&per_page=1");
					const reports = await api<Page<never>>("/reports?per_page=1");
					const scholars = await api<Page<never>>("/scholars?per_page=1");
					if (!cancelled)
						setCounts([
							{ label: "Reports awaiting my action", num: pending.total, href: "/reports?state=submitted" },
							{ label: "All my scholars' reports", num: reports.total, href: "/reports" },
							{ label: "My scholars", num: scholars.total, href: "/scholars" },
						]);
				} else {
					const scholars = await api<Page<never>>("/scholars?per_page=1");
					const supervisors = await api<Page<never>>("/supervisors?per_page=1");
					const pending = await api<Page<never>>("/reports?state=submitted&per_page=1");
					if (!cancelled)
						setCounts([
							{ label: "Registered scholars", num: scholars.total, href: "/scholars" },
							{ label: "Supervisors", num: supervisors.total, href: "/supervisors" },
							{ label: "APRs awaiting approval", num: pending.total, href: "/reports?state=submitted" },
						]);
				}
			} catch (err) {
				if (!cancelled) setError(err instanceof ApiError ? err.message : "Could not load the dashboard");
			}
		})();
		return () => {
			cancelled = true;
		};
	}, [user]);

	return (
		<>
			<PageHeader
				title={`Welcome, ${user?.full_name ?? ""}`}
				sub={
					user?.role === "scholar"
						? "Your supervision record — reports, meetings, milestones."
						: user?.role === "supervisor"
							? "Your scholars' reports and meetings."
							: "The department register at a glance."
				}
			/>
			<ErrorText>{error}</ErrorText>
			<div className="count-grid">
				{counts.map((c) => (
					<Link key={c.label} href={c.href} className="count-cell">
						<span className="num">{c.num}</span>
						<span className="lbl">{c.label}</span>
					</Link>
				))}
			</div>
		</>
	);
}

