"use client";

import Link from "next/link";
import { useCustom } from "@refinedev/core";

import { useAuth } from "@/lib/auth";
import { Card, ErrorState, PageHeader, queryError, StatCard } from "@/components/ui";
import { BarChart } from "@/components/tabs";

interface UpcomingMeeting {
	id: string;
	scholar_id: string;
	scholar_name: string;
	meeting_date: string;
	agenda: string | null;
}

interface Activity {
	id: number;
	at: string;
	table_name: string;
	action: string;
	actor_role: string;
}

interface Dashboard {
	scholars: number;
	supervisors: number;
	reports_by_state: Record<string, number>;
	scholars_by_stage: Record<string, number>;
	upcoming_meetings: UpcomingMeeting[];
	recent_activity: Activity[];
}

/** One endpoint, role-scoped server-side — the same payload renders differently
 * per role. recent_activity is admin-only (SECURITY.md §2). */
export default function DashboardPage() {
	const { user } = useAuth();
	const { query } = useCustom<Dashboard>({ url: "/stats/dashboard", method: "get" });

	if (query.isLoading) return <p className="soft">Loading…</p>;
	if (query.error) return <ErrorState>{queryError(query.error)}</ErrorState>;

	const d = query.data?.data;
	if (!d || !user) return null;

	const pending = d.reports_by_state["submitted"] ?? 0;
	const reportsTotal = Object.values(d.reports_by_state).reduce((a, b) => a + b, 0);
	const isScholar = user.role === "scholar";

	const cards = isScholar
		? [
				{ num: reportsTotal, label: "My progress reports", href: "/reports" },
				{ num: pending, label: "Awaiting approval", href: "/reports" },
				{ num: d.upcoming_meetings.length, label: "Upcoming meetings", href: "/meetings" },
			]
		: user.role === "supervisor"
			? [
					{ num: d.scholars, label: "My scholars", href: "/scholars" },
					{ num: pending, label: "Reports awaiting my action", href: "/reports" },
					{ num: reportsTotal, label: "All my scholars' reports", href: "/reports" },
				]
			: [
					{ num: d.scholars, label: "Registered scholars", href: "/scholars" },
					{ num: d.supervisors, label: "Supervisors", href: "/supervisors" },
					{ num: pending, label: "APRs awaiting approval", href: "/reports" },
				];

	return (
		<>
			<PageHeader
				title={`Welcome, ${user.full_name}`}
				sub={
					isScholar
						? "Your supervision record — reports, meetings, milestones."
						: user.role === "supervisor"
							? "Your scholars' reports and meetings."
							: "The department register at a glance."
				}
			/>
			<div className="count-grid">
				{cards.map((c) => (
					<StatCard key={c.label} num={c.num} label={c.label} href={c.href} />
				))}
			</div>
			<div className="stack">
				<Card>
					<h2>{isScholar ? "My stage" : "Scholars by stage"}</h2>
					<BarChart data={Object.entries(d.scholars_by_stage).map(([label, count]) => ({ label, count }))} />
				</Card>
				<Card>
					<h2>Upcoming meetings</h2>
					{d.upcoming_meetings.length === 0 ? (
						<p className="soft">Nothing scheduled.</p>
					) : (
						<ul>
							{d.upcoming_meetings.map((m) => (
								<li key={m.id}>
									<Link href={`/scholars/${m.scholar_id}`}>{m.scholar_name}</Link> — {m.meeting_date}
									{m.agenda ? ` · ${m.agenda}` : ""}
								</li>
							))}
						</ul>
					)}
				</Card>
				{user.role === "admin" && (
					<Card>
						<h2>Recent activity</h2>
						{d.recent_activity.length === 0 ? (
							<p className="soft">No recorded activity yet.</p>
						) : (
							<ul>
								{d.recent_activity.map((a) => (
									<li key={a.id}>
										<span className="faint">{new Date(a.at).toLocaleString()}</span> — {a.action} on {a.table_name} ({a.actor_role})
									</li>
								))}
							</ul>
						)}
					</Card>
				)}
			</div>
		</>
	);
}