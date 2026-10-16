"use client";

/** Per-record comment thread + attachment panel. Both are polymorphic: the API
 * gates every route through the target record, so these components need no
 * role logic beyond author/uploader-or-admin delete visibility. */

import { Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, apiDownload, apiUpload, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, EmptyState, ErrorText } from "./ui";

interface Comment {
	id: string;
	author_id: string;
	body: string;
	created_at: string;
}

const errMsg = (err: unknown, fallback: string) => (err instanceof ApiError ? err.message : fallback);

export function CommentThread({ tableName, recordId }: { tableName: string; recordId: string }) {
	const { user } = useAuth();
	const [items, setItems] = useState<Comment[]>([]);
	const [body, setBody] = useState("");
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);

	const load = useCallback(async () => {
		try {
			setItems(await api<Comment[]>(`/comments?table_name=${tableName}&record_id=${recordId}`));
		} catch (err) {
			setError(errMsg(err, "Could not load comments"));
		}
	}, [tableName, recordId]);

	useEffect(() => {
		void load();
	}, [load]);

	async function post() {
		setBusy(true);
		setError("");
		try {
			await api("/comments", {
				method: "POST",
				body: JSON.stringify({ table_name: tableName, record_id: recordId, body: body.trim() }),
			});
			setBody("");
			await load();
		} catch (err) {
			setError(errMsg(err, "Could not post the comment"));
		} finally {
			setBusy(false);
		}
	}

	async function remove(id: string) {
		setError("");
		try {
			await api(`/comments/${id}`, { method: "DELETE" });
			await load();
		} catch (err) {
			setError(errMsg(err, "Could not delete the comment"));
		}
	}

	return (
		<div className="stack">
			<form
				className="comment-form"
				onSubmit={(e) => {
					e.preventDefault();
					if (body.trim()) void post();
				}}
			>
				<textarea
					rows={3}
					placeholder="Add a comment…"
					aria-label="Add a comment"
					value={body}
					onChange={(e) => setBody(e.target.value)}
					maxLength={4000}
				/>
				<Button type="submit" kind="primary" size="sm" disabled={busy}>
					{busy ? "Posting…" : "Comment"}
				</Button>
			</form>
			<ErrorText>{error}</ErrorText>
			{items.length === 0 ? (
				<EmptyState>No comments yet.</EmptyState>
			) : (
				<ul className="comment-list">
					{items.map((c) => (
						<li key={c.id} className="comment-item">
							<div>
								<p>{c.body}</p>
								<span className="faint">{new Date(c.created_at).toLocaleString()}</span>
							</div>
							{(user?.id === c.author_id || user?.role === "admin") && (
								<Button size="sm" kind="ghost" onClick={() => void remove(c.id)} aria-label="Delete comment">
									<Trash2 size={14} aria-hidden />
								</Button>
							)}
						</li>
					))}
				</ul>
			)}
		</div>
	);
}

interface Attachment {
	id: string;
	file_name: string;
	content_type: string;
	size_bytes: number;
	uploaded_by: string;
	created_at: string;
}

const kb = (n: number) => (n >= 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`);

export function AttachmentsPanel({ tableName, recordId }: { tableName: string; recordId: string }) {
	const { user } = useAuth();
	const [items, setItems] = useState<Attachment[]>([]);
	const [error, setError] = useState("");
	const [busy, setBusy] = useState(false);

	const load = useCallback(async () => {
		try {
			setItems(await api<Attachment[]>(`/attachments?table_name=${tableName}&record_id=${recordId}`));
		} catch (err) {
			setError(errMsg(err, "Could not load documents"));
		}
	}, [tableName, recordId]);

	useEffect(() => {
		void load();
	}, [load]);

	async function upload(file: File) {
		setBusy(true);
		setError("");
		try {
			await apiUpload("/attachments", file, { table_name: tableName, record_id: recordId });
			await load();
		} catch (err) {
			setError(errMsg(err, "Could not upload the file"));
		} finally {
			setBusy(false);
		}
	}

	async function remove(id: string) {
		setError("");
		try {
			await api(`/attachments/${id}`, { method: "DELETE" });
			await load();
		} catch (err) {
			setError(errMsg(err, "Could not delete the document"));
		}
	}

	return (
		<div className="stack">
			<label className="btn btn-primary btn-sm" style={{ alignSelf: "flex-start" }}>
				{busy ? "Uploading…" : "Upload document"}
				<input
					type="file"
					hidden
					disabled={busy}
					onChange={(e) => {
						const file = e.target.files?.[0];
						e.target.value = ""; // allow re-picking the same file
						if (file) void upload(file);
					}}
				/>
			</label>
			<span className="faint">PDF, images, documents — up to 2 MB each.</span>
			<ErrorText>{error}</ErrorText>
			{items.length === 0 ? (
				<EmptyState>No documents attached.</EmptyState>
			) : (
				<ul className="comment-list">
					{items.map((a) => (
						<li key={a.id} className="comment-item">
							<div>
								<p>
									<a
										href="#"
										onClick={(e) => {
											e.preventDefault();
											void apiDownload(`/attachments/${a.id}/download`, a.file_name);
										}}
									>
										{a.file_name}
									</a>
								</p>
								<span className="faint">
									{a.content_type} · {kb(a.size_bytes)} · {new Date(a.created_at).toLocaleDateString()}
								</span>
							</div>
							{(user?.id === a.uploaded_by || user?.role === "admin") && (
								<Button size="sm" kind="ghost" onClick={() => void remove(a.id)} aria-label={`Delete ${a.file_name}`}>
									<Trash2 size={14} aria-hidden />
								</Button>
							)}
						</li>
					))}
				</ul>
			)}
		</div>
	);
}