"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, StateBadge, Table } from "@/lib/ui";

interface Report {
	id: string;
	report_year: number;
	period: string;
	summary: string;
	state: "draft" | "submitted" | "approved" | "rejected";
}

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
}

const STATES = ["", "draft", "submitted", "approved", "rejected"];
const PERIODS = ["January-June", "July-December"];
const EMPTY_FORM = { scholar_id: "", report_year: String(new Date().getFullYear()), period: PERIODS[0], summary: "" };

export default function ReportsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Report[]>([]);
	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [stateFilter, setStateFilter] = useState("");
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	async function load() {
		try {
			const q = new URLSearchParams({ per_page: "100", ...(stateFilter ? { state: stateFilter } : {}) });
			const page = await api<{ items: Report[] }>(`/reports?${q}`);
			setItems(page.items);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load reports");
		}
	}

	useEffect(() => {
		if (!user) return;
		void load();
		if (user.role === "admin") {
			// only the admin form picks a scholar; the scholar form uses the caller's own id
			api<{ items: Scholar[] }>("/scholars?per_page=100")
				.then((p) => setScholars(p.items))
				.catch(() => undefined);
		}
	}, [user, stateFilter]);

	async function create() {
		setFormError("");
		try {
			await api("/reports", {
				method: "POST",
				body: JSON.stringify({
					scholar_id: user?.role === "scholar" ? user.scholar_id : form.scholar_id,
					report_year: Number(form.report_year),
					period: form.period,
					summary: form.summary,
				}),
			});
			setForm(EMPTY_FORM);
			setShowForm(false);
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not create the report");
		}
	}

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader title="Progress reports" sub="Annual progress reports (APR)" />
				<div className="page-actions">
					<select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} aria-label="Filter by state">
						{STATES.map((s) => (
							<option key={s} value={s}>
								{s || "All states"}
							</option>
						))}
					</select>
					{/* scholars author APRs; supervisors only act on them (RBAC MATRIX) */}
					{user?.role !== "supervisor" && (
						<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Close" : "New report"}</Button>
					)}
				</div>
			</div>
			<ErrorText>{error}</ErrorText>
			{showForm && (
				<form
					className="form-card stack"
					onSubmit={(e) => {
						e.preventDefault();
						void create();
					}}
				>
					{user?.role === "admin" && (
						<Field label="Scholar">
							<select required value={form.scholar_id} onChange={(e) => setForm({ ...form, scholar_id: e.target.value })}>
								<option value="">— select —</option>
								{scholars.map((s) => (
									<option key={s.id} value={s.id}>
										{s.scholar_name} ({s.roll_number})
									</option>
								))}
							</select>
						</Field>
					)}
					<Field label="Report year">
						<input
							required
							type="number"
							min={2000}
							max={2100}
							value={form.report_year}
							onChange={(e) => setForm({ ...form, report_year: e.target.value })}
						/>
					</Field>
					<Field label="Period">
						<select value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })}>
							{PERIODS.map((p) => (
								<option key={p}>{p}</option>
							))}
						</select>
					</Field>
					<Field label="Summary of progress">
						<textarea required rows={6} value={form.summary} onChange={(e) => setForm({ ...form, summary: e.target.value })} />
					</Field>
					<ErrorText>{formError}</ErrorText>
					<Button type="submit" kind="primary">Create draft</Button>
				</form>
			)}
			<Table
				head={["Year", "Period", "Summary", "State", ""]}
				rows={items.map((r) => [
					String(r.report_year),
					r.period,
					r.summary.length > 80 ? `${r.summary.slice(0, 80)}…` : r.summary,
					<StateBadge state={r.state} />,
					<Link href={`/reports/${r.id}`}>Open →</Link>,
				])}
				empty="No reports yet."
			/>
		</>
	);
}