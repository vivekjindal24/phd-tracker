"use client";

/** Primitives over the tokens in globals.css. State is conveyed by text first,
   color second (DESIGN_SYSTEM principle); no control renders without real behavior. */

import { type MouseEvent, type ReactNode } from "react";

type ButtonProps = {
	children: ReactNode;
	onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
	kind?: "primary" | "secondary" | "ghost" | "danger";
	size?: "sm" | "md";
	disabled?: boolean;
	type?: "button" | "submit";
};

export function Button({ children, onClick, kind = "secondary", size = "md", disabled, type = "button" }: ButtonProps) {
	return (
		<button type={type} className={`btn btn-${kind} ${size === "sm" ? "btn-sm" : ""}`} onClick={onClick} disabled={disabled}>
			{children}
		</button>
	);
}

const STATE_CLASS: Record<string, string> = {
	approved: "ok",
	Approved: "ok",
	submitted: "warn",
	Pending: "warn",
	rejected: "bad",
	Rejected: "bad",
};

/** Report state / milestone status badge. Unknown values fall back to neutral. */
export function Badge({ value, tone }: { value: string; tone?: "accent" }) {
	const cls = tone === "accent" ? "accent" : (STATE_CLASS[value] ?? "");
	return (
		<span className={`badge ${cls}`}>
			<span className="badge-dot" aria-hidden />
			{value}
		</span>
	);
}

export function Field({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
	return (
		<label className="field">
			<span className="field-label">{label}</span>
			{children}
			{help && <span className="field-help">{help}</span>}
		</label>
	);
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
	return <div className={`card ${className ?? ""}`}>{children}</div>;
}

export function StatCard({ num, label, href }: { num: number | string; label: string; href: string }) {
	return (
		<a className="card stat-card" href={href}>
			<span className="stat-num">{num}</span>
			<span className="stat-label">{label}</span>
		</a>
	);
}

export function PageHeader({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
	return (
		<header className="page-head">
			<div>
				<h1>{title}</h1>
				{sub && <p className="page-sub">{sub}</p>}
			</div>
			{actions && <div className="page-actions">{actions}</div>}
		</header>
	);
}

export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
	return (
		<div className="table-wrap" aria-busy style={{ padding: "0.75rem", display: "grid", gap: "0.9rem" }}>
			{Array.from({ length: rows }).map((_, r) => (
				// biome-ignore lint/suspicious/noArrayIndexKey: static placeholder rows
				<div key={r} style={{ display: "flex", gap: "0.75rem" }}>
					{Array.from({ length: cols }).map((_, c) => (
						// biome-ignore lint/suspicious/noArrayIndexKey: static placeholder cells
						<span key={c} className="skeleton" style={{ height: "0.9rem", flex: 1 }} />
					))}
				</div>
			))}
		</div>
	);
}

export function EmptyState({ children }: { children: ReactNode }) {
	return <div className="empty-state">{children}</div>;
}

export function ErrorState({ children }: { children: ReactNode }) {
	return (
		<div className="error-state" role="alert">
			{children}
		</div>
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

/** react-query error (HttpError/ApiError) → user-facing message. */
export function queryError(e: unknown): string | undefined {
	if (!e) return undefined;
	return e instanceof Error ? e.message : String(e);
}

export function Note({ children }: { children: ReactNode }) {
	return <div className="note">{children}</div>;
}