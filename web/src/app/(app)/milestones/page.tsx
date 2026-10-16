"use client";

import { useEffect, useState } from "react";

import { api, ApiError, exportDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, StateBadge, Table } from "@/lib/ui";

interface Milestone {
	id: string;
	scholar_id: string;
	milestone_type: string;
	status: "Pending" | "Approved" | "Rejected";
	approval_body: string | null;
	resolution_number: string | null;
	resolution_date: string | null;
	notes: string | null;
}

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
	department: string;
}

const TYPES = [
	"Coursework Completion",
	"Proposal Approval (RDC)",
	"Pre-Synopsis Seminar",
	"Thesis Submission",
	"Viva Voce",
	"Degree Awarded",
];
const EMPTY_FORM = { scholar_id: "", milestone_type: TYPES[0], resolution_number: "", notes: "" };

export default function MilestonesPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Milestone[]>([]);
	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	async function load() {
		try {
			const page = await api<{ items: Milestone[] }>("/milestones?per_page=100");
			setItems(page.items);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load milestones");
		}
	}

	useEffect(() => {
		if (!user) return;
		void load();
		if (user.role !== "scholar") {
			api<{ items: Scholar[] }>("/scholars?per_page=100")
				.then((p) => setScholars(p.items))
				.catch(() => undefined);
		}
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
			await load();
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

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader title="Milestones" sub="The milestone register" />
				<div className="page-actions">
					{user?.role === "admin" && (
						<>
							<Button kind="ghost" onClick={() => void download("pdf")}>Register PDF</Button>
							<Button kind="ghost" onClick={() => void download("csv")}>Register CSV</Button>
						</>
					)}
					{user?.role !== "scholar" && <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Close" : "Record milestone"}</Button>}
				</div>
			</div>
			<ErrorText>{error}</ErrorText>
			{showForm && user?.role !== "scholar" && (
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
					<Button type="submit" kind="primary">Save milestone</Button>
				</form>
			)}
			<Table
				head={["Milestone", "Status", "Resolution", "Date", "Notes"]}
				rows={items.map((m) => [
					m.milestone_type,
					<StateBadge state={m.status} />,
					m.resolution_number ?? "—",
					m.resolution_date ?? "—",
					m.notes ?? "—",
				])}
				empty="No milestones recorded yet."
			/>
		</>
	);
}