"use client";

import { useEffect, useState } from "react";

import { useTable } from "@refinedev/core";

import { api, ApiError } from "@/lib/api";
import { Button, ErrorText, Field, PageHeader, queryError } from "@/components/ui";
import { Column, DataTable, Pager } from "@/components/data-table";
import { Dialog } from "@/components/overlay";

interface Meeting {
	id: string;
	scholar_id: string;
	meeting_date: string;
	agenda: string | null;
	minutes: string | null;
	action_items: string | null;
}

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
	supervisor_id: string | null;
}

const EMPTY_FORM = { scholar_id: "", meeting_date: "", agenda: "", minutes: "", action_items: "" };

export default function MeetingsPage() {
	const { tableQuery, sorters, setSorters, filters, setFilters, currentPage, setCurrentPage, pageSize } = useTable({
		resource: "meetings",
		pagination: { pageSize: 20 },
		sorters: { initial: [{ field: "meeting_date", order: "desc" }] },
	});

	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	useEffect(() => {
		// filter + counterparty pick from the caller's own scoped list
		api<{ items: Scholar[] }>("/scholars?per_page=100")
			.then((p) => setScholars(p.items))
			.catch(() => setScholars([]));
	}, []);

	async function create() {
		setFormError("");
		try {
			const scholar = scholars.find((s) => s.id === form.scholar_id);
			if (!scholar?.supervisor_id) {
				setFormError("That scholar has no supervisor assigned yet.");
				return;
			}
			await api("/meetings", {
				method: "POST",
				body: JSON.stringify({
					scholar_id: form.scholar_id,
					supervisor_id: scholar.supervisor_id,
					meeting_date: form.meeting_date,
					agenda: form.agenda || null,
					minutes: form.minutes || null,
					action_items: form.action_items || null,
				}),
			});
			setForm(EMPTY_FORM);
			setShowForm(false);
			await tableQuery.refetch();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not record the meeting");
		}
	}

	type EqFilter = { field: string; operator: "eq"; value: unknown };
	const scholarFilter = filters.find((f): f is EqFilter => "field" in f && f.field === "scholar_id");
	const columns: Column<Meeting>[] = [
		{ key: "date", head: "Date", sort: "meeting_date", cell: (m) => m.meeting_date },
		{ key: "agenda", head: "Agenda", cell: (m) => m.agenda ?? "—" },
		{ key: "minutes", head: "Minutes", cell: (m) => m.minutes ?? "—" },
		{ key: "actions", head: "Action items", cell: (m) => m.action_items ?? "—" },
	];

	return (
		<>
			<PageHeader
				title="Meetings"
				sub="Supervision meeting record"
				actions={<Button kind="primary" onClick={() => setShowForm(true)}>Record meeting</Button>}
			/>
			<div className="toolbar">
				<label className="field">
					<span className="field-label">Scholar</span>
					<select
						value={scholarFilter ? String(scholarFilter.value ?? "") : ""}
						onChange={(e) =>
							setFilters(
								e.target.value ? [{ field: "scholar_id", operator: "eq", value: e.target.value }] : [],
								"replace",
							)
						}
					>
						<option value="">All scholars</option>
						{scholars.map((s) => (
							<option key={s.id} value={s.id}>
								{s.scholar_name} ({s.roll_number})
							</option>
						))}
					</select>
				</label>
			</div>
			<DataTable
				columns={columns}
				rows={(tableQuery.data?.data as Meeting[] | undefined) ?? []}
				rowId={(m) => m.id}
				loading={tableQuery.isLoading}
				error={queryError(tableQuery.error)}
				empty="No meetings recorded yet."
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
				<Dialog title="Record meeting" onClose={() => setShowForm(false)}>
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
						<Field label="Date">
							<input
								required
								type="date"
								value={form.meeting_date}
								onChange={(e) => setForm({ ...form, meeting_date: e.target.value })}
							/>
						</Field>
						<Field label="Agenda">
							<input value={form.agenda} onChange={(e) => setForm({ ...form, agenda: e.target.value })} />
						</Field>
						<Field label="Minutes">
							<textarea rows={4} value={form.minutes} onChange={(e) => setForm({ ...form, minutes: e.target.value })} />
						</Field>
						<Field label="Action items">
							<textarea rows={2} value={form.action_items} onChange={(e) => setForm({ ...form, action_items: e.target.value })} />
						</Field>
						<ErrorText>{formError}</ErrorText>
						<div className="form-actions">
							<Button onClick={() => setShowForm(false)}>Cancel</Button>
							<Button type="submit" kind="primary">
								Save record
							</Button>
						</div>
					</form>
				</Dialog>
			)}
		</>
	);
}