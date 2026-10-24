"use client";

import { useRef, useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
import type { FileItem, FileOwner } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./attachments.css";

type Upload = { file_id: string; upload_url: string; method: string; headers: Record<string, string> };

function size(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Files on a record (PRD F13). The API decides who may see, add or remove them; the bytes go
 *  straight to object storage on a presigned URL, then the API confirms they arrived. */
export function Attachments({
  table,
  recordId,
  canUpload,
  title = "Files",
  hint,
}: {
  table: FileOwner;
  recordId: string;
  canUpload: boolean;
  title?: string;
  hint?: string;
}) {
  const { data, error, reload } = useFetch<FileItem[]>(`/files?table_name=${table}&record_id=${recordId}`);
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actError, setActError] = useState<string | null>(null);

  async function upload(file: File) {
    setBusy(`Uploading ${file.name}…`);
    setActError(null);
    try {
      const start = await api<Upload>("/files/uploads", {
        method: "POST",
        body: JSON.stringify({
          table_name: table,
          record_id: recordId,
          file_name: file.name,
          content_type: file.type || "application/octet-stream",
          size_bytes: file.size,
        }),
      });
      let put: Response;
      try {
        put = await fetch(start.upload_url, { method: start.method, headers: start.headers, body: file });
      } catch {
        throw new ApiError(0, "storage_unreachable", "The file store could not be reached. Please try again.");
      }
      if (!put.ok) throw new ApiError(put.status, "storage_rejected", `The file store refused the upload (${put.status}).`);
      await api(`/files/${start.file_id}/complete`, { method: "POST" });
      await reload();
    } catch (e) {
      setActError(errorText(e));
    } finally {
      setBusy(null);
      if (input.current) input.current.value = "";
    }
  }

  async function open(file: FileItem) {
    setActError(null);
    try {
      const { url } = await api<{ url: string }>(`/files/${file.id}/download`);
      window.location.assign(url);
    } catch (e) {
      setActError(errorText(e));
    }
  }

  async function remove(file: FileItem) {
    setActError(null);
    try {
      await api(`/files/${file.id}`, { method: "DELETE" });
      await reload();
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <Card className="attachments">
      <h2>{title}</h2>
      {hint && <p className="muted">{hint}</p>}
      <ErrorText>{error}</ErrorText>
      {data && data.length === 0 && <p className="muted">No files yet.</p>}
      {data && data.length > 0 && (
        <ul className="file-list">
          {data.map((f) => (
            <li key={f.id}>
              <button type="button" className="file-name" onClick={() => open(f)}>{f.file_name}</button>
              <span className="muted">{size(f.size_bytes)} · {new Date(f.created_at).toLocaleDateString()}</span>
              {canUpload && <Button kind="ghost" onClick={() => remove(f)}>Remove</Button>}
            </li>
          ))}
        </ul>
      )}
      {canUpload && (
        <label className="file-add">
          <span className="btn btn-secondary">{busy ?? "Add a file"}</span>
          <input ref={input} type="file" className="visually-hidden" disabled={busy !== null}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); }} />
        </label>
      )}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
