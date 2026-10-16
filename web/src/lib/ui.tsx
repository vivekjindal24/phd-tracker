"use client";

/** The register kit: headers, rule-separated tables, print-like badges.
   State is always conveyed by text first, color second (DESIGN_SYSTEM §15). */

import { type ReactNode } from "react";

export function PageHeader({ title, sub }: { title: string; sub?: ReactNode }) {
	return (
		<header className="page-head">
			<h1>{title}</h1>
			{sub && <p className="soft">{sub}</p>}
		</header>
	);
}

export function Table({ head, rows, empty }: { head: string[]; rows: ReactNode[][]; empty?: string }) {
	if (rows.length === 0) {
		return <p className="soft empty">{empty ?? "No records yet."}</p>;
	}
	return (
		<div className="table-wrap">
			<table>
				<thead>
					<tr>{head.map((h) => <th key={h}>{h}</th>)}</tr>
				</thead>
				<tbody>
					{rows.map((row, i) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: rows are static renders
						<tr key={i}>
							{row.map((cell, j) => <td key={j}>{cell}</td>)}
						</tr>
					))}
				</tbody>
			</table>
		</div>
	);
}

const STATE_LABEL: Record<string, string> = {
	draft: "Draft",
	submitted: "Submitted",
	approved: "Approved",
	rejected: "Rejected",
	Pending: "Pending",
	Approved: "Approved",
};

export function StateBadge({ state }: { state: string }) {
	const cls = state === "approved" || state === "Approved" ? "ok" : state === "rejected" || state === "Rejected" ? "bad" : state === "submitted" || state === "Pending" ? "warn" : "";
	return (
		<span className={`badge ${cls}`}>
			<span className="badge-dot" aria-hidden />
			{STATE_LABEL[state] ?? state}
		</span>
	);
}

export function Button({
	children,
	onClick,
	kind = "primary",
	disabled,
	type = "button",
}: {
	children: ReactNode;
	onClick?: () => void;
	kind?: "primary" | "ghost" | "danger";
	disabled?: boolean;
	type?: "button" | "submit";
}) {
	return (
		<button
			type={type}
			className={`btn btn-${kind}`}
			onClick={onClick}
			disabled={disabled}
		>
			{children}
		</button>
	);
}

export function Field({
	label,
	children,
}: {
	label: string;
	children: ReactNode;
}) {
	return (
		<label className="field">
			<span className="field-label">{label}</span>
			{children}
		</label>
	);
}

export function ErrorText({ children }: { children: ReactNode }) {
	if (!children) return null;
	return (
		<p className="error-text" role="alert">
			{children}
		</p>
	);
}