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

const EMPTY_FORM = { full_name: "", email: "", department: "", designation: "Assistant Professor", max_scholars: "8" };

export default function SupervisorsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Supervisor[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [editing, setEditing] = useState<Supervisor | null>(null);
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

	function openCreate() {
		setEditing(null);
		setForm(EMPTY_FORM);
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
			setForm(EMPTY_FORM);
			setEditing(null);
			setShowForm(false);
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not save the supervisor");
		}
	}

	async function remove(s: Supervisor) {
		if (!window.confirm(`Remove ${s.full_name}? (Soft-delete — audit trail preserved; no data is lost.)`)) return;
		setError("");
		try {
			await api(`/supervisors/${s.id}`, { method: "DELETE" });
			await load();
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not remove the supervisor");
		}
	}

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader title="Supervisors" sub="Faculty directory with UGC supervision caps" />
				{user?.role === "admin" && (
					<div className="page-actions">
						{showForm ? (
							<Button onClick={() => setShowForm(false)}>Close</Button>
						) : (
							<Button onClick={openCreate}>New supervisor</Button>
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
					<h2>{editing ? `Edit ${editing.full_name}` : "Add supervisor"}</h2>
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
					<Button type="submit" kind="primary">{editing ? "Save changes" : "Add supervisor"}</Button>
				</form>
			)}
			<Table
				head={["Name", "Email", "Department", "Designation", "Cap", ...(user?.role === "admin" ? ["Actions"] : [])]}
				rows={items.map((s) => [
					s.full_name,
					s.email,
					s.department,
					s.designation,
					String(s.max_scholars),
					...(user?.role === "admin"
						? [
								<Button key="edit" kind="ghost" onClick={() => startEdit(s)}>Edit</Button>,
								<Button key="del" kind="danger" onClick={() => void remove(s)}>Delete</Button>,
							]
						: []),
				])}
				empty="No supervisors registered."
			/>
		</>
	);
}