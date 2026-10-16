"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, ErrorText, Field, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { Dialog } from "@/components/overlay";

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

const STATES = ["draft", "submitted", "approved", "rejected"] as const;
const PERIODS = ["January-June", "July-December"];
const EMPTY_FORM = { scholar_id: "", report_year: String(new Date().getFullYear()), period: PERIODS[0], summary: "" };

export default function ReportsPage() {
	const { user } = useAuth();
	const router = useRouter();
	const { tableQuery, sorters, setSorters, filters, setFilters, currentPage, setCurrentPage, pageSize } = useTable({
		resource: "reports",
		pagination: { pageSize: 20 },
		sorters: { initial: [{ field: "created_at", order: "desc" }] },
	});

	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	useEffect(() => {
		if (user?.role !== "admin") return;
		// only the admin form picks a scholar; the scholar form uses the caller's own id
		api<{ items: Scholar[] }>("/scholars?per_page=100")
			.then((p) => setScholars(p.items))
			.catch(() => setScholars([]));
	}, [user]);

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
			await tableQuery.refetch();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not create the report");
		}
	}

	type EqFilter = { field: string; operator: "eq"; value: unknown };
	const stateFilter = filters.find((f): f is EqFilter => "field" in f && f.field === "state");
	const columns: Column<Report>[] = [
		{ key: "year", head: "Year", sort: "report_year", cell: (r) => String(r.report_year) },
		{ key: "period", head: "Period", cell: (r) => r.period },
		{
			key: "summary",
			head: "Summary",
			cell: (r) => (r.summary.length > 80 ? `${r.summary.slice(0, 80)}…` : r.summary),
		},
		{ key: "state", head: "State", sort: "state", cell: (r) => <Badge value={r.state} /> },
	];

	return (
		<>
			<PageHeader
				title="Progress reports"
				sub="Annual progress reports (APR)"
				actions={
					// scholars author APRs; supervisors only act on them (RBAC MATRIX)
					user?.role !== "supervisor" && (
						<Button kind="primary" onClick={() => setShowForm(true)}>
							New report
						</Button>
					)
				}
			/>
			<div className="toolbar" role="group" aria-label="Filter by state">
				<button type="button" className="chip" aria-pressed={!stateFilter} onClick={() => setFilters([], "replace")}>
					All
				</button>
				{STATES.map((s) => (
					<button
						key={s}
						type="button"
						className="chip"
						aria-pressed={stateFilter?.value === s}
						onClick={() => setFilters([{ field: "state", operator: "eq", value: s }], "replace")}
					>
						{s}
					</button>
				))}
			</div>
			<DataTable
				columns={columns}
				rows={(tableQuery.data?.data as Report[] | undefined) ?? []}
				rowId={(r) => r.id}
				loading={tableQuery.isLoading}
				error={queryError(tableQuery.error)}
				empty="No reports yet."
				sort={sorters[0]}
				onSort={(s) => setSorters([s])}
				onRowClick={(r) => router.push(`/reports/${r.id}`)}
				footer={
					<Pager
						page={currentPage}
						perPage={pageSize}
						total={tableQuery.data?.total ?? 0}
						onPage={setCurrentPage}
					/>
				}
			/>
			{showForm && (
				<Dialog title="New progress report" onClose={() => setShowForm(false)}>
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
						<div className="form-actions">
							<Button onClick={() => setShowForm(false)}>Cancel</Button>
							<Button type="submit" kind="primary">
								Create draft
							</Button>
						</div>
					</form>
				</Dialog>
			)}
		</>
	);
}