"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError, exportDownload } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Badge, Button, ErrorText, Field, PageHeader } from "@/components/ui";
import { ConfirmDialog } from "@/components/overlay";
import { Tabs } from "@/components/tabs";
import { AttachmentsPanel, CommentThread } from "@/components/record-panels";

interface Report {
	id: string;
	report_year: number;
	period: string;
	summary: string;
	supervisor_comment: string | null;
	approved_on: string | null;
	state: "draft" | "submitted" | "approved" | "rejected";
	created_at: string;
	updated_at: string;
}

/** What the workflow state machine allows (TRANSITIONS in workflow.py) — the
 * API is the enforcer; this only decides which buttons to draw. */
function allowedActions(state: Report["state"], role: string): { action: string; label: string }[] {
	const out: { action: string; label: string }[] = [];
	if (state === "draft" && (role === "scholar" || role === "admin")) out.push({ action: "submit", label: "Submit for approval" });
	if (state === "submitted" && (role === "supervisor" || role === "admin")) {
		out.push({ action: "approve", label: "Approve" }, { action: "send_back", label: "Send back" });
	}
	if (state === "rejected" && (role === "scholar" || role === "admin")) out.push({ action: "resubmit", label: "Resubmit" });
	return out;
}

export default function ReportDetailPage() {
	const { user } = useAuth();
	const params = useParams<{ id: string }>();
	const router = useRouter();
	const [report, setReport] = useState<Report | null>(null);
	const [error, setError] = useState("");
	const [actionError, setActionError] = useState("");
	const [comment, setComment] = useState("");
	const [saving, setSaving] = useState(false);
	const [confirmDelete, setConfirmDelete] = useState(false);

	const load = useCallback(async () => {
		try {
			setReport(await api<Report>(`/reports/${params.id}`));
		} catch (err) {
			setError(err instanceof ApiError ? err.message : "Could not load the report");
		}
	}, [params.id]);

	useEffect(() => {
		if (params?.id) void load();
	}, [params, load]);

	async function doAction(action: string) {
		setActionError("");
		setSaving(true);
		try {
			setReport(await api<Report>(`/reports/${params.id}/${action}`, { method: "POST" }));
		} catch (err) {
			setActionError(err instanceof ApiError ? err.message : "Action failed");
		} finally {
			setSaving(false);
		}
	}

	async function saveComment() {
		setActionError("");
		setSaving(true);
		try {
			setReport(
				await api<Report>(`/reports/${params.id}`, {
					method: "PATCH",
					body: JSON.stringify({ supervisor_comment: comment }),
				}),
			);
			setComment("");
		} catch (err) {
			setActionError(err instanceof ApiError ? err.message : "Could not save the comment");
		} finally {
			setSaving(false);
		}
	}

	async function saveSummary(next: string) {
		setActionError("");
		setSaving(true);
		try {
			setReport(await api<Report>(`/reports/${params.id}`, { method: "PATCH", body: JSON.stringify({ summary: next }) }));
		} catch (err) {
			setActionError(err instanceof ApiError ? err.message : "Could not save the summary");
		} finally {
			setSaving(false);
		}
	}

	async function downloadPdf() {
		setActionError("");
		try {
			await exportDownload(`/export/reports/${params.id}.pdf`, `APR-${params.id}.pdf`);
		} catch (err) {
			setActionError(err instanceof ApiError ? err.message : "Export failed");
		}
	}

	async function remove() {
		setActionError("");
		try {
			await api(`/reports/${params.id}`, { method: "DELETE" });
			router.push("/reports");
		} catch (err) {
			setActionError(err instanceof ApiError ? err.message : "Delete failed");
			setConfirmDelete(false);
		}
	}

	if (error) {
		return (
			<>
				<PageHeader title="Progress report" />
				<ErrorText>{error}</ErrorText>
				<Link href="/reports">← Back to reports</Link>
			</>
		);
	}
	if (!report || !user) return <p className="soft">Loading…</p>;

	const canEditSummary =
		report.state !== "approved" &&
		(user.role === "admin" || (user.role === "scholar" && (report.state === "draft" || report.state === "rejected")));
	const canComment = user.role === "supervisor" && report.state === "submitted";
	const actions = allowedActions(report.state, user.role);

	const overview = (
		<div className="stack">
			<dl className="kv">
				<dt>Approved on</dt>
				<dd>{report.approved_on ?? "—"}</dd>
				<dt>Created</dt>
				<dd>{new Date(report.created_at).toLocaleString()}</dd>
				<dt>Last updated</dt>
				<dd>{new Date(report.updated_at).toLocaleString()}</dd>
			</dl>
			{canEditSummary ? (
				<SummaryEditor summary={report.summary} disabled={saving} onSave={(v) => void saveSummary(v)} />
			) : (
				<section>
					<h2>Summary of progress</h2>
					<p className="note">{report.summary}</p>
				</section>
			)}
			<section>
				<h2>Supervisor comment</h2>
				{report.supervisor_comment && <p className="note">{report.supervisor_comment}</p>}
				{canComment && (
					<form
						className="form-card stack"
						onSubmit={(e) => {
							e.preventDefault();
							if (comment.trim()) void saveComment();
						}}
					>
						<Field label="Comment visible to the scholar">
							<textarea required rows={4} value={comment} onChange={(e) => setComment(e.target.value)} />
						</Field>
						<Button type="submit" kind="primary" disabled={saving}>
							Save comment
						</Button>
					</form>
				)}
			</section>
			{actions.length > 0 && (
				<div className="toolbar">
					{actions.map((a) => (
						<Button key={a.action} kind="primary" disabled={saving} onClick={() => void doAction(a.action)}>
							{a.label}
						</Button>
					))}
				</div>
			)}
		</div>
	);

	return (
		<>
			<PageHeader
				title={`APR ${report.report_year} · ${report.period}`}
				sub={<Badge value={report.state} />}
				actions={
					<>
						{user.role === "admin" && report.state === "approved" && (
							<Button size="sm" onClick={() => void downloadPdf()}>
								Download PDF
							</Button>
						)}
						{user.role === "admin" && (
							<Button size="sm" kind="danger" onClick={() => setConfirmDelete(true)}>
								Delete
							</Button>
						)}
						<Link href="/reports" className="btn btn-ghost btn-sm">
							← Reports
						</Link>
					</>
				}
			/>
			<ErrorText>{actionError}</ErrorText>
			<Tabs
				tabs={[
					{ id: "overview", label: "Overview", panel: overview },
					{
						id: "comments",
						label: "Comments",
						panel: <CommentThread tableName="progress_reports" recordId={report.id} />,
					},
					{
						id: "documents",
						label: "Documents",
						panel: <AttachmentsPanel tableName="progress_reports" recordId={report.id} />,
					},
				]}
			/>
			{confirmDelete && (
				<ConfirmDialog
					title="Delete this report?"
					message="Soft-delete — the audit trail is preserved; no data is lost."
					onConfirm={() => void remove()}
					onCancel={() => setConfirmDelete(false)}
				/>
			)}
		</>
	);
}

function SummaryEditor({ summary, disabled, onSave }: { summary: string; disabled: boolean; onSave: (v: string) => void }) {
	const [text, setText] = useState(summary);
	useEffect(() => setText(summary), [summary]);
	return (
		<section>
			<h2>Summary of progress</h2>
			<form
				className="form-card stack"
				onSubmit={(e) => {
					e.preventDefault();
					if (text.trim()) onSave(text);
				}}
			>
				<textarea required rows={8} value={text} onChange={(e) => setText(e.target.value)} />
				<Button type="submit" kind="primary" disabled={disabled}>
					Save summary
				</Button>
			</form>
		</section>
	);
}