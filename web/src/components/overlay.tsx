"use client";

/** Overlays: Dialog (focus-trap-lite via autoFocus), ConfirmDialog for destructive
 * actions, DropdownMenu with click-outside close. */

import { MenuIcon } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { Button } from "./ui";

export function Dialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
	const ref = useRef<HTMLDivElement>(null);
	useEffect(() => {
		ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
		const onKey = (e: KeyboardEvent) => {
			if (e.key === "Escape") onClose();
		};
		document.addEventListener("keydown", onKey);
		return () => document.removeEventListener("keydown", onKey);
	}, [onClose]);

	return (
		<div className="dialog-backdrop" onClick={(e) => (e.target === e.currentTarget ? onClose() : null)}>
			<div className="dialog" role="dialog" aria-modal aria-label={title} ref={ref}>
				<h2>{title}</h2>
				{children}
			</div>
		</div>
	);
}

export function ConfirmDialog({
	title,
	message,
	confirmLabel = "Delete",
	onConfirm,
	onCancel,
}: {
	title: string;
	message: ReactNode;
	confirmLabel?: string;
	onConfirm: () => void;
	onCancel: () => void;
}) {
	return (
		<Dialog title={title} onClose={onCancel}>
			<p className="soft">{message}</p>
			<div className="form-actions">
				<Button onClick={onCancel}>Cancel</Button>
				<Button kind="danger" onClick={onConfirm}>
					{confirmLabel}
				</Button>
			</div>
		</Dialog>
	);
}

export function DropdownMenu({
	label,
	children,
	align = "right",
}: {
	label: ReactNode;
	children: ReactNode;
	align?: "right" | "left";
}) {
	const [open, setOpen] = useState(false);
	const ref = useRef<HTMLDivElement>(null);
	useEffect(() => {
		if (!open) return;
		const onDoc = (e: MouseEvent) => {
			if (!ref.current?.contains(e.target as Node)) setOpen(false);
		};
		document.addEventListener("click", onDoc);
		return () => document.removeEventListener("click", onDoc);
	}, [open]);

	return (
		<div className="menu-wrap" ref={ref}>
			<button
				type="button"
				className="btn btn-ghost btn-sm"
				aria-haspopup="menu"
				aria-expanded={open}
				onClick={() => setOpen((v) => !v)}
			>
				{label}
				<MenuIcon size={14} aria-hidden />
			</button>
			{open && (
				<div className="menu" style={align === "left" ? { left: 0, right: "auto" } : undefined} role="menu">
					{children}
				</div>
			)}
		</div>
	);
}