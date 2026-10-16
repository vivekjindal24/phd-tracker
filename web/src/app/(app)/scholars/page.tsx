"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, Table } from "@/lib/ui";

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
	department: string;
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
	stage: "",
};

export default function ScholarsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Scholar[]>([]);
	const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [editing, setEditing] = useState<Scholar | null>(null);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	async function load() {
		try {
			const page = await api<{ items: Scholar[]; total: number }>("/scholars?per_page=100");
			setItems(page.items);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load scholars");
		}
	}

	useEffect(() => {
		if (!user) return;
		if (user.role === "admin") {
			api<{ items: Supervisor[] }>("/supervisors?per_page=100")
				.then((p) => setSupervisors(p.items))
				.catch(() => undefined); // directory pick optional for the form
		}
		void load();
	}, [user]);

	function openCreate() {
		setEditing(null);
		setForm(EMPTY_FORM);
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
			setForm(EMPTY_FORM);
			setEditing(null);
			setShowForm(false);
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not save the scholar");
		}
	}

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader
					title="Scholars"
					sub={user?.role === "supervisor" ? "Scholars under your supervision" : "Registered research scholars"}
				/>
				{user?.role === "admin" && (
					<div className="page-actions">
						{showForm ? (
							<Button onClick={() => setShowForm(false)}>Close</Button>
						) : (
							<Button onClick={openCreate}>New scholar</Button>
						)}
					</div>
				)}
			</div>
			<ErrorText>{error}</ErrorText>
			{showForm && user?.role === "admin" && (
				<form
					className="form-card stack"
					onSubmit={(e) => {
						e.preventDefault();
						void submit();
					}}
				>
					<h2>{editing ? `Edit ${editing.scholar_name}` : "Register scholar"}</h2>
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
						<select
							value={form.supervisor_id}
							onChange={(e) => setForm({ ...form, supervisor_id: e.target.value })}
						>
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
					<Button type="submit" kind="primary">{editing ? "Save changes" : "Register scholar"}</Button>
				</form>
			)}
			<Table
				head={["Roll number", "Name", "Department", "Stage", "Admitted", ...(user?.role === "admin" ? ["Actions"] : [])]}
				rows={items.map((s) => [
					s.roll_number,
					s.scholar_name,
					s.department,
					s.stage,
					s.admission_date,
					...(user?.role === "admin"
						? [<Button key="edit" kind="ghost" onClick={() => startEdit(s)}>Edit</Button>]
						: []),
				])}
				empty="No scholars visible to you yet."
			/>
			<p className="soft" style={{ fontSize: "0.8rem" }}>
				<Link href="/search">Search scholars by name or roll number →</Link>
			</p>
		</>
	);
}