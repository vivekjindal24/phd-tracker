"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, ErrorText, Field, PageHeader, Table } from "@/lib/ui";

interface Meeting {
	id: string;
	scholar_id: string;
	supervisor_id: string;
	meeting_date: string;
	agenda: string | null;
	minutes: string | null;
	action_items: string | null;
	next_meeting_date: string | null;
}

interface Scholar {
	id: string;
	scholar_name: string;
	roll_number: string;
	supervisor_id: string | null;
}

const EMPTY_FORM = { scholar_id: "", meeting_date: "", agenda: "", minutes: "", action_items: "" };

export default function MeetingsPage() {
	const { user } = useAuth();
	const [items, setItems] = useState<Meeting[]>([]);
	const [scholars, setScholars] = useState<Scholar[]>([]);
	const [error, setError] = useState("");
	const [showForm, setShowForm] = useState(false);
	const [form, setForm] = useState(EMPTY_FORM);
	const [formError, setFormError] = useState("");

	async function load() {
		try {
			const page = await api<{ items: Meeting[] }>("/meetings?per_page=100");
			setItems(page.items);
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load meetings");
		}
	}

	useEffect(() => {
		if (!user) return;
		void load();
		// scholar/supervisor pick the counterparty from their own scoped list
		if (user.role !== "admin") {
			api<{ items: Scholar[] }>("/scholars?per_page=100")
				.then((p) => setScholars(p.items))
				.catch(() => undefined);
		}
	}, [user]);

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
			await load();
		} catch (err) {
			setFormError(err instanceof ApiError ? err.message : "Could not record the meeting");
		}
	}

	return (
		<>
			<div className="page-head page-head-row">
				<PageHeader title="Meetings" sub="Supervision meeting record" />
				<div className="page-actions">
					<Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Close" : "Record meeting"}</Button>
				</div>
			</div>
			<ErrorText>{error}</ErrorText>
			{showForm && (
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
					<Button type="submit" kind="primary">Save record</Button>
				</form>
			)}
			<Table
				head={["Date", "Agenda", "Minutes", "Action items"]}
				rows={items.map((m) => [m.meeting_date, m.agenda ?? "—", m.minutes ?? "—", m.action_items ?? "—"])}
				empty="No meetings recorded yet."
			/>
		</>
	);
}