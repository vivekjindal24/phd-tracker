"use client";

import Link from "next/link";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, EmptyState, ErrorText, PageHeader } from "@/components/ui";

interface SearchResults {
	scholars: { id: string; scholar_name: string; roll_number: string; department: string }[];
	supervisors: { id: string; full_name: string; department: string; designation: string }[];
	meetings: { id: string; meeting_date: string; agenda: string | null }[];
	reports: { id: string; report_year: number; period: string; state: string; summary: string }[];
	milestones: { id: string; milestone_type: string; status: string }[];
}

function ResultSection({ title, children }: { title: string; children: React.ReactNode }) {
	return (
		<Card>
			<h2>{title}</h2>
			{children}
		</Card>
	);
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
					className="field"
					style={{ flex: 1 }}
					value={q}
					onChange={(e) => setQ(e.target.value)}
					placeholder="Name, roll number, department…"
					aria-label="Search query"
				/>
				<Button type="submit" kind="primary" disabled={busy}>
					{busy ? "Searching…" : "Search"}
				</Button>
			</form>
			<ErrorText>{error}</ErrorText>
			{results && (
				<div className="stack">
					<ResultSection title="Scholars">
						{results.scholars.length === 0 ? (
							<EmptyState>No matches.</EmptyState>
						) : (
							<ul>
								{results.scholars.map((s) => (
									<li key={s.id}>
										<Link href={`/scholars/${s.id}`}>{s.scholar_name}</Link> — {s.roll_number} · {s.department}
									</li>
								))}
							</ul>
						)}
					</ResultSection>
					<ResultSection title="Supervisors">
						{results.supervisors.length === 0 ? (
							<EmptyState>No matches.</EmptyState>
						) : (
							<ul>
								{results.supervisors.map((s) => (
									<li key={s.id}>
										{s.full_name} — {s.designation} · {s.department}
									</li>
								))}
							</ul>
						)}
					</ResultSection>
					<ResultSection title="Reports">
						{results.reports.length === 0 ? (
							<EmptyState>No matches.</EmptyState>
						) : (
							<ul>
								{results.reports.map((r) => (
									<li key={r.id}>
										<Link href={`/reports/${r.id}`}>
											{r.report_year} {r.period}
										</Link>{" "}
										<Badge value={r.state} /> — {r.summary.slice(0, 60)}
										{r.summary.length > 60 ? "…" : ""}
									</li>
								))}
							</ul>
						)}
					</ResultSection>
					<ResultSection title="Meetings">
						{results.meetings.length === 0 ? (
							<EmptyState>No matches.</EmptyState>
						) : (
							<ul>
								{results.meetings.map((m) => (
									<li key={m.id}>
										{m.meeting_date} — {m.agenda ?? "(no agenda)"}
									</li>
								))}
							</ul>
						)}
					</ResultSection>
					<ResultSection title="Milestones">
						{results.milestones.length === 0 ? (
							<EmptyState>No matches.</EmptyState>
						) : (
							<ul>
								{results.milestones.map((m) => (
									<li key={m.id}>
										{m.milestone_type} — <Badge value={m.status} />
									</li>
								))}
							</ul>
						)}
					</ResultSection>
				</div>
			)}
		</>
	);
}