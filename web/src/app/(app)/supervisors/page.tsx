"use client";

import { useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { ConfirmDialog, Dialog } from "@/components/overlay";

interface Supervisor {
	id: string;
	full_name: string;
	email: string;
	department: string;
	designation: string;
	max_scholars: number;
}

const DESIGNATIONS = ["Professor", "Associate Professor", "Assistant Professor"];
const EMPTY_FORM = { full_name: "", email: "", department: "", designation: "Assistant Professor", max_scholars: "8" };

export default function SupervisorsPage() {
	const { user } = useAuth();
	const { tableQuery, sorters, setSorters, filters, setFilters, currentPage, setCurrentPage, pageSize } = useTable({
		resource: "supervisors",
		pagination: { pageSize: 20 },
		sorters: { initial: [{ field: "full_name", order: "asc" }] },
	});

	const [showForm, setShowForm] = useState(false);
	const [editing, setEditing] = useState<Supervisor | null>(null);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");
	const [deleting, setDeleting] = useState<Supervisor | null>(null);
	const [deleteError, setDeleteError] = useState("");

	const isAdmin = user?.role === "admin";

	function openCreate() {
		setEditing(null);
		setForm(EMPTY_FORM);
		setFormError("");
		setShowForm(true);
	}

	function startEdit(s: Supervisor) {
		setEditing(s);
		setForm({
			full_name: s.full_name,
			email: s.email,
			department: s.department,
			designation: s.designation,
			max_scholars: String(s.max_scholars),
		});
		setFormError("");
		setShowForm(true);
	}

	async function submit() {
		setFormError("");
		const body = { ...form, max_scholars: Number(form.max_scholars) };
		try {
			if (editing) {
				await api(`/supervisors/${editing.id}`, { method: "PATCH", body: JSON.stringify(body) });
			} else {
				await api("/supervisors", { method: "POST", body: JSON.stringify(body) });
			}
			setShowForm(false);
			setEditing(null);
			await tableQuery.refetch();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not save the supervisor");
		}
	}

	async function remove() {
		if (!deleting) return;
		setDeleteError("");
		try {
			await api(`/supervisors/${deleting.id}`, { method: "DELETE" });
			setDeleting(null);
			await tableQuery.refetch();
		} catch (err) {
			setDeleteError(err instanceof ApiError ? err.message : "Could not remove the supervisor");
		}
	}

	function setDesignationFilter(designation: string) {
		setFilters(designation ? [{ field: "designation", operator: "eq", value: designation }] : [], "replace");
	}

	type EqFilter = { field: string; operator: "eq"; value: unknown };
	const designationFilter = filters.find((f): f is EqFilter => "field" in f && f.field === "designation");
	const columns: Column<Supervisor>[] = [
		{ key: "name", head: "Name", sort: "full_name", cell: (s) => s.full_name },
		{ key: "email", head: "Email", cell: (s) => s.email },
		{ key: "dept", head: "Department", sort: "department", cell: (s) => s.department },
		{ key: "desig", head: "Designation", sort: "designation", cell: (s) => s.designation },
		{ key: "cap", head: "Cap", cell: (s) => String(s.max_scholars) },
		...(isAdmin
			? [
					{
						key: "actions",
						head: "",
						cell: (s: Supervisor) => (
							<span style={{ display: "flex", gap: "0.25rem" }}>
								<Button
									size="sm"
									kind="ghost"
									onClick={() => {
										startEdit(s);
									}}
								>
									Edit
								</Button>
								<Button
									size="sm"
									kind="ghost"
									onClick={() => {
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
				title="Supervisors"
				sub="Faculty directory with UGC supervision caps"
				actions={isAdmin && <Button kind="primary" onClick={openCreate}>New supervisor</Button>}
			/>
			<div className="toolbar">
				<label className="field">
					<span className="field-label">Designation</span>
					<select
						value={designationFilter ? String(designationFilter.value ?? "") : ""}
						onChange={(e) => setDesignationFilter(e.target.value)}
					>
						<option value="">All designations</option>
						{DESIGNATIONS.map((d) => (
							<option key={d}>{d}</option>
						))}
					</select>
				</label>
			</div>
			<DataTable
				columns={columns}
				rows={(tableQuery.data?.data as Supervisor[] | undefined) ?? []}
				rowId={(s) => s.id}
				loading={tableQuery.isLoading}
				error={queryError(tableQuery.error)}
				empty="No supervisors registered."
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
			{showForm && (
				<Dialog title={editing ? `Edit ${editing.full_name}` : "Add supervisor"} onClose={() => setShowForm(false)}>
					<form
						className="form-card stack"
						onSubmit={(e) => {
							e.preventDefault();
							void submit();
						}}
					>
						<Field label="Name">
							<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
						</Field>
						<Field label="Email">
							<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
						</Field>
						<Field label="Department">
							<input required value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
						</Field>
						<Field label="Designation">
							<select value={form.designation} onChange={(e) => setForm({ ...form, designation: e.target.value })}>
								{DESIGNATIONS.map((d) => (
									<option key={d}>{d}</option>
								))}
							</select>
						</Field>
						<Field label="Supervision cap (max scholars)">
							<input
								required
								type="number"
								min={1}
								max={8}
								value={form.max_scholars}
								onChange={(e) => setForm({ ...form, max_scholars: e.target.value })}
							/>
						</Field>
						<ErrorText>{formError}</ErrorText>
						<div className="form-actions">
							<Button onClick={() => setShowForm(false)}>Cancel</Button>
							<Button type="submit" kind="primary">
								{editing ? "Save changes" : "Add supervisor"}
							</Button>
						</div>
					</form>
				</Dialog>
			)}
			{deleting && (
				<ConfirmDialog
					title={`Remove ${deleting.full_name}?`}
					message="Soft-delete — the audit trail is preserved; no data is lost."
					onConfirm={() => void remove()}
					onCancel={() => setDeleting(null)}
				/>
			)}
			<ErrorText>{deleteError}</ErrorText>
		</>
	);
}