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

const EMPTY_FORM = {
	scholar_name: "",
	roll_number: "",
	department: "",
	admission_date: "",
	supervisor_id: "",
};

export default function ScholarsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Scholar[]>([]);
	const [supervisors, setSupervisors] = useState<Supervisor[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
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

	async function create() {
		setFormError("");
		try {
			await api("/scholars", {
				method: "POST",
				body: JSON.stringify({
					scholar_name: form.scholar_name,
					roll_number: form.roll_number,
					department: form.department,
					admission_date: form.admission_date,
					...(form.supervisor_id ? { supervisor_id: form.supervisor_id } : {}),
				}),
			});
			setForm(EMPTY_FORM);
			setShowForm(false);
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not create the scholar");
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
						<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Close" : "New scholar"}</Button>
					</div>
				)}
			</div>
			<ErrorText>{error}</ErrorText>
			{showForm && user?.role === "admin" && (
				<form
					className="form-card stack"
					onSubmit={(e) => {
						e.preventDefault();
						void create();
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
					<ErrorText>{formError}</ErrorText>
					<Button type="submit" kind="primary">Register scholar</Button>
				</form>
			)}
			<Table
				head={["Roll number", "Name", "Department", "Stage", "Admitted"]}
				rows={items.map((s) => [
					s.roll_number,
					s.scholar_name,
					s.department,
					s.stage,
					s.admission_date,
				])}
				empty="No scholars visible to you yet."
			/>
			<p className="soft" style={{ fontSize: "0.8rem" }}>
				<Link href="/search">Search scholars by name or roll number →</Link>
			</p>
		</>
	);
}