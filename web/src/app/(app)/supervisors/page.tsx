"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, Table } from "@/lib/ui";

interface Supervisor {
	id: string;
	full_name: string;
	email: string;
	department: string;
	designation: string;
	max_scholars: number;
}

const EMPTY_FORM = { full_name: "", email: "", department: "", designation: "Assistant Professor" };

export default function SupervisorsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Supervisor[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	async function load() {
		try {
			const page = await api<{ items: Supervisor[] }>("/supervisors?per_page=100");
			setItems(page.items);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load supervisors");
		}
	}

	useEffect(() => {
		void load();
	}, []);

	async function create() {
		setFormError("");
		try {
			await api("/supervisors", { method: "POST", body: JSON.stringify(form) });
			setForm(EMPTY_FORM);
			setShowForm(false);
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not create the supervisor");
		}
	}

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader title="Supervisors" sub="Faculty directory with UGC supervision caps" />
				{user?.role === "admin" && (
					<div className="page-actions">
						<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Close" : "New supervisor"}</Button>
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
						<input required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />
					</Field>
					<Field label="Email">
						<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
					</Field>
					<Field label="Department">
						<input required value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
					</Field>
					<Field label="Designation">
						<select
							value={form.designation}
							onChange={(e) => setForm({ ...form, designation: e.target.value })}
						>
							<option>Professor</option>
							<option>Associate Professor</option>
							<option>Assistant Professor</option>
						</select>
					</Field>
					<ErrorText>{formError}</ErrorText>
					<Button type="submit" kind="primary">Add supervisor</Button>
				</form>
			)}
			<Table
				head={["Name", "Email", "Department", "Designation", "Cap"]}
				rows={items.map((s) => [s.full_name, s.email, s.department, s.designation, String(s.max_scholars)])}
				empty="No supervisors registered."
			/>
		</>
	);
}