"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, ErrorText, Field, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { ConfirmDialog, Dialog } from "@/components/overlay";

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
	department: string;
	stage: string;
	supervisor_id: string | null;
	admission_date: string;
}

interface Supervisor {
	id: string;
	full_name: string;
	designation: string;
}

const STAGES = [
	"Registered",
	"Coursework",
	"Proposal Approved",
	"Research Phase",
	"Pre-Synopsis Done",
	"Thesis Submitted",
	"Viva Voce",
	"Degree Awarded",
];

const EMPTY_FORM = {
	scholar_name: "",
	roll_number: "",
	department: "",
	admission_date: "",
	supervisor_id: "",
	stage: "Registered",
};

export default function ScholarsPage() {
	const { user } = useAuth();
	const router = useRouter();
	const { tableQuery, sorters, setSorters, filters, setFilters, currentPage, setCurrentPage, pageSize } = useTable({
		resource: "scholars",
		pagination: { pageSize: 20 },
		sorters: { initial: [{ field: "created_at", order: "desc" }] },
	});

	const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
	const [showForm, setShowForm] = useState(false);
	const [editing, setEditing] = useState<Scholar | null>(null);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");
	const [deleting, setDeleting] = useState<Scholar | null>(null);
	const [deleteError, setDeleteError] = useState("");

	const isAdmin = user?.role === "admin";

	useEffect(() => {
		if (!isAdmin) return;
		api<{ items: Supervisor[] }>("/supervisors?per_page=100")
			.then((p) => setSupervisors(p.items))
			.catch(() => setSupervisors([])); // pick list is optional for the form
	}, [isAdmin]);

	function openCreate() {
		setEditing(null);
		setForm(EMPTY_FORM);
		setFormError("");
		setShowForm(true);
	}

	function startEdit(s: Scholar) {
		setEditing(s);
		setForm({
			scholar_name: s.scholar_name,
			roll_number: s.roll_number,
			department: s.department,
			admission_date: s.admission_date,
			supervisor_id: s.supervisor_id ?? "",
			stage: s.stage,
		});
		setFormError("");
		setShowForm(true);
	}

	async function submit() {
		setFormError("");
		const body = {
			scholar_name: form.scholar_name,
			roll_number: form.roll_number,
			department: form.department,
			admission_date: form.admission_date,
			supervisor_id: form.supervisor_id || null,
			...(editing ? { stage: form.stage } : {}),
		};
		try {
			if (editing) {
				await api(`/scholars/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
			} else {
				await api("/scholars", { method: "POST", body: JSON.stringify(body) });
			}
			setShowForm(false);
			setEditing(null);
			await tableQuery.refetch();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not save the scholar");
		}
	}

	async function remove() {
		if (!deleting) return;
		setDeleteError("");
		try {
			await api(`/scholars/${deleting.id}`, { method: "DELETE" });
			setDeleting(null);
			await tableQuery.refetch();
		} catch (err) {
			setDeleteError(err instanceof ApiError ? err.message : "Could not remove the scholar");
		}
	}

	function setStageFilter(stage: string) {
		setFilters(stage ? [{ field: "stage", operator: "eq", value: stage }] : [], "replace");
	}

	type EqFilter = { field: string; operator: "eq"; value: unknown };
	const stageFilter = filters.find((f): f is EqFilter => "field" in f && f.field === "stage");
	const columns: Column<Scholar>[] = [
		{ key: "roll", head: "Roll number", sort: "roll_number", cell: (s) => s.roll_number },
		{ key: "name", head: "Name", sort: "scholar_name", cell: (s) => s.scholar_name },
		{ key: "dept", head: "Department", sort: "department", cell: (s) => s.department },
		{ key: "stage", head: "Stage", sort: "stage", cell: (s) => <Badge value={s.stage} tone="accent" /> },
		{ key: "adm", head: "Admitted", sort: "admission_date", cell: (s) => s.admission_date },
		...(isAdmin
			? [
					{
						key: "actions",
						head: "",
						cell: (s: Scholar) => (
							<span style={{ display: "flex", gap: "0.25rem" }}>
								<Button
									size="sm"
									kind="ghost"
									onClick={(e) => {
										e.stopPropagation();
										startEdit(s);
									}}
								>
									Edit
								</Button>
								<Button
									size="sm"
									kind="ghost"
									onClick={(e) => {
										e.stopPropagation();
										setDeleteError("");
										setDeleting(s);
									}}
								>
									Delete
								</Button>
							</span>
						),
					},
				]
			: []),
	];

	return (
		<>
			<PageHeader
				title="Scholars"
				sub={user?.role === "supervisor" ? "Scholars under your supervision" : "Registered research scholars"}
				actions={isAdmin && <Button kind="primary" onClick={openCreate}>New scholar</Button>}
			/>
			<div className="toolbar">
				<label className="field">
					<span className="field-label">Stage</span>
					<select
						value={stageFilter ? String(stageFilter.value ?? "") : ""}
						onChange={(e) => setStageFilter(e.target.value)}
					>
						<option value="">All stages</option>
						{STAGES.map((s) => (
							<option key={s}>{s}</option>
						))}
					</select>
				</label>
			</div>
			<DataTable
				columns={columns}
				rows={(tableQuery.data?.data as Scholar[] | undefined) ?? []}
				rowId={(s) => s.id}
				loading={tableQuery.isLoading}
				error={queryError(tableQuery.error)}
				empty="No scholars visible to you yet."
				sort={sorters[0]}
				onSort={(s) => setSorters([s])}
				onRowClick={(s) => router.push(`/scholars/${s.id}`)}
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
				<Dialog title={editing ? `Edit ${editing.scholar_name}` : "Register scholar"} onClose={() => setShowForm(false)}>
					<form
						className="form-card stack"
						onSubmit={(e) => {
							e.preventDefault();
							void submit();
						}}
					>
						<Field label="Name">
							<input required value={form.scholar_name} onChange={(e) => setForm({ ...form, scholar_name: e.target.value })} />
						</Field>
						<Field label="Roll number">
							<input required value={form.roll_number} onChange={(e) => setForm({ ...form, roll_number: e.target.value })} />
						</Field>
						<Field label="Department">
							<input required value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
						</Field>
						<Field label="Admission date">
							<input
								required
								type="date"
								value={form.admission_date}
								onChange={(e) => setForm({ ...form, admission_date: e.target.value })}
							/>
						</Field>
						<Field label="Supervisor">
							<select value={form.supervisor_id} onChange={(e) => setForm({ ...form, supervisor_id: e.target.value })}>
								<option value="">— none —</option>
								{supervisors.map((s) => (
									<option key={s.id} value={s.id}>
										{s.full_name} ({s.designation})
									</option>
								))}
							</select>
						</Field>
						{editing && (
							<Field label="Stage">
								<select required value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>
									{STAGES.map((s) => (
										<option key={s}>{s}</option>
									))}
								</select>
							</Field>
						)}
						<ErrorText>{formError}</ErrorText>
						<div className="form-actions">
							<Button onClick={() => setShowForm(false)}>Cancel</Button>
							<Button type="submit" kind="primary">
								{editing ? "Save changes" : "Register scholar"}
							</Button>
						</div>
					</form>
				</Dialog>
			)}
			{deleting && (
				<ConfirmDialog
					title={`Remove ${deleting.scholar_name}?`}
					message="Soft-delete — the audit trail is preserved; no data is lost."
					onConfirm={() => void remove()}
					onCancel={() => setDeleting(null)}
				/>
			)}
			<ErrorText>{deleteError}</ErrorText>
		</>
	);
}