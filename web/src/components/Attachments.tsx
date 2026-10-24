"use client";

import { useRef, useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { FileItem, FileOwner } from "@/lib/types";
import { openFile, uploadFile } from "@/lib/upload";
import { errorText, useFetch } from "@/lib/useFetch";
import "./attachments.css";

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
      await uploadFile(table, recordId, file);
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
      await openFile(file.id);
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
