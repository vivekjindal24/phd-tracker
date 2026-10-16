"use client";

import Link from "next/link";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { Button, ErrorText, PageHeader, StateBadge } from "@/lib/ui";

interface SearchResults {
	scholars: { id: string; scholar_name: string; roll_number: string; department: string }[];
	supervisors: { id: string; full_name: string; department: string; designation: string }[];
	meetings: { id: string; meeting_date: string; agenda: string | null }[];
	reports: { id: string; report_year: number; period: string; state: string; summary: string }[];
	milestones: { id: string; milestone_type: string; status: string }[];
}

export default function SearchPage() {
	const [q, setQ] = useState("");
	const [results, setResults] = useState<SearchResults | null>(null);
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);

	async function run() {
		if (!q.trim()) return;
		setError("");
		setBusy(true);
		try {
			setResults(await api<SearchResults>(`/search?q=${encodeURIComponent(q.trim())}`));
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Search failed");
		} finally {
			setBusy(false);
		}
	}

	return (
		<>
			<PageHeader title="Search" sub="Scholars, supervisors, meetings, reports, milestones" />
			<form
				className="toolbar"
				onSubmit={(e) => {
					e.preventDefault();
					void run();
				}}
			>
				<input
					value={q}
					onChange={(e) => setQ(e.target.value)}
					placeholder="Name, roll number, department…"
					aria-label="Search query"
					style={{ flex: 1, minWidth: "16rem" }}
				/>
				<Button type="submit" kind="primary" disabled={busy}>
					{busy ? "Searching…" : "Search"}
				</Button>
			</form>
			<ErrorText>{error}</ErrorText>
			{results && (
				<div className="stack">
					<section>
						<h2>Scholars</h2>
						<ul>
							{results.scholars.map((s) => (
								<li key={s.id}>
									{s.scholar_name} — {s.roll_number} · {s.department}
								</li>
							))}
							{results.scholars.length === 0 && <li className="soft">No matches.</li>}
						</ul>
					</section>
					<section>
						<h2>Supervisors</h2>
						<ul>
							{results.supervisors.map((s) => (
								<li key={s.id}>
									{s.full_name} — {s.designation} · {s.department}
								</li>
							))}
							{results.supervisors.length === 0 && <li className="soft">No matches.</li>}
						</ul>
					</section>
					<section>
						<h2>Reports</h2>
						<ul>
							{results.reports.map((r) => (
								<li key={r.id}>
									<Link href={`/reports/${r.id}`}>
										{r.report_year} {r.period}
									</Link>{" "}
									<StateBadge state={r.state} /> — {r.summary.slice(0, 60)}
									{r.summary.length > 60 ? "…" : ""}
								</li>
							))}
							{results.reports.length === 0 && <li className="soft">No matches.</li>}
						</ul>
					</section>
					<section>
						<h2>Meetings</h2>
						<ul>
							{results.meetings.map((m) => (
								<li key={m.id}>
									{m.meeting_date} — {m.agenda ?? "(no agenda)"}
								</li>
							))}
							{results.meetings.length === 0 && <li className="soft">No matches.</li>}
						</ul>
					</section>
					<section>
						<h2>Milestones</h2>
						<ul>
							{results.milestones.map((m) => (
								<li key={m.id}>
									{m.milestone_type} — <StateBadge state={m.status} />
								</li>
							))}
							{results.milestones.length === 0 && <li className="soft">No matches.</li>}
						</ul>
					</section>
				</div>
			)}
		</>
	);
}