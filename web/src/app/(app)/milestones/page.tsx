"use client";

import { useEffect, useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError, exportDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, ErrorText, Field, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { Dialog } from "@/components/overlay";

interface Milestone {
	id: string;
	milestone_type: string;
	status: "Pending" | "Approved" | "Rejected";
	resolution_number: string | null;
	resolution_date: string | null;
	notes: string | null;
}

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
}

const TYPES = [
	"Coursework Completion",
	"Proposal Approval (RDC)",
	"Pre-Synopsis Seminar",
	"Thesis Submission",
	"Viva Voce",
	"Degree Awarded",
];
const STATUSES = ["Pending", "Approved", "Rejected"] as const;
const EMPTY_FORM = { scholar_id: "", milestone_type: TYPES[0], resolution_number: "", notes: "" };

export default function MilestonesPage() {
	const { user } = useAuth();
	const { tableQuery, sorters, setSorters, filters, setFilters, currentPage, setCurrentPage, pageSize } = useTable({
		resource: "milestones",
		pagination: { pageSize: 20 },
		sorters: { initial: [{ field: "created_at", order: "desc" }] },
	});

	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");
	const [error, setError] = useState("");

	useEffect(() => {
		if (user?.role === "scholar") return;
		api<{ items: Scholar[] }>("/scholars?per_page=100")
			.then((p) => setScholars(p.items))
			.catch(() => setScholars([]));
	}, [user]);

	async function create() {
		setFormError("");
		try {
			await api("/milestones", {
				method: "POST",
				body: JSON.stringify({
					scholar_id: form.scholar_id,
					milestone_type: form.milestone_type,
					resolution_number: form.resolution_number || null,
					notes: form.notes || null,
				}),
			});
			setForm(EMPTY_FORM);
			setShowForm(false);
			await tableQuery.refetch();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not record the milestone");
		}
	}

	async function download(kind: "pdf" | "csv") {
		setError("");
		try {
			await exportDownload(`/export/milestones.${kind}`, `milestone-register.${kind}`);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Export failed");
		}
	}

	type EqFilter = { field: string; operator: "eq"; value: unknown };
	const statusFilter = filters.find((f): f is EqFilter => "field" in f && f.field === "status");
	const columns: Column<Milestone>[] = [
		{ key: "type", head: "Milestone", sort: "milestone_type", cell: (m) => m.milestone_type },
		{ key: "status", head: "Status", sort: "status", cell: (m) => <Badge value={m.status} /> },
		{ key: "res", head: "Resolution", sort: "resolution_date", cell: (m) => m.resolution_number ?? "—" },
		{ key: "date", head: "Date", sort: "resolution_date", cell: (m) => m.resolution_date ?? "—" },
		{ key: "notes", head: "Notes", cell: (m) => m.notes ?? "—" },
	];

	return (
		<>
			<PageHeader
				title="Milestones"
				sub="The milestone register"
				actions={
					<>
						{user?.role === "admin" && (
							<>
								<Button size="sm" kind="ghost" onClick={() => void download("pdf")}>Register PDF</Button>
								<Button size="sm" kind="ghost" onClick={() => void download("csv")}>Register CSV</Button>
							</>
						)}
						{user?.role !== "scholar" && (
							<Button kind="primary" onClick={() => setShowForm(true)}>Record milestone</Button>
						)}
					</>
				}
			/>
			<div className="toolbar" role="group" aria-label="Filter by status">
				<button
					type="button"
					className="chip"
					aria-pressed={!statusFilter}
					onClick={() => setFilters([], "replace")}
				>
					All
				</button>
				{STATUSES.map((s) => (
					<button
						key={s}
						type="button"
						className="chip"
						aria-pressed={statusFilter?.value === s}
						onClick={() => setFilters([{ field: "status", operator: "eq", value: s }], "replace")}
					>
						{s}
					</button>
				))}
			</div>
			<ErrorText>{error}</ErrorText>
			<DataTable
				columns={columns}
				rows={(tableQuery.data?.data as Milestone[] | undefined) ?? []}
				rowId={(m) => m.id}
				loading={tableQuery.isLoading}
				error={queryError(tableQuery.error)}
				empty="No milestones recorded yet."
				sort={sorters[0]}
				onSort={(s) => setSorters([s])}
				footer={
					<Pager
						page={currentPage}
						perPage={pageSize}
						total={tableQuery.data?.total ?? 0}
						onPage={setCurrentPage}
					/>
				}
			/>
			{showForm && user?.role !== "scholar" && (
				<Dialog title="Record milestone" onClose={() => setShowForm(false)}>
					<form
						className="form-card stack"
						onSubmit={(e) => {
							e.preventDefault();
							void create();
						}}
					>
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
						<Field label="Milestone">
							<select value={form.milestone_type} onChange={(e) => setForm({ ...form, milestone_type: e.target.value })}>
								{TYPES.map((t) => (
									<option key={t}>{t}</option>
								))}
							</select>
						</Field>
						<Field label="Resolution number">
							<input value={form.resolution_number} onChange={(e) => setForm({ ...form, resolution_number: e.target.value })} />
						</Field>
						<Field label="Notes">
							<textarea rows={3} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
						</Field>
						<ErrorText>{formError}</ErrorText>
						<div className="form-actions">
							<Button onClick={() => setShowForm(false)}>Cancel</Button>
							<Button type="submit" kind="primary">
								Save milestone
							</Button>
						</div>
					</form>
				</Dialog>
			)}
		</>
	);
}