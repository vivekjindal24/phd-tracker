"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Comments } from "@/components/Comments";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { DOC_KIND_LABELS } from "@/lib/types";
import type { DocumentItem } from "@/lib/types";
import { openFile, uploadFile } from "@/lib/upload";
import { errorText, useFetch } from "@/lib/useFetch";
import "@/components/attachments.css";
import "@/components/items/items.css";
import "./document.css";

function NewVersion({ doc, onSaved }: { doc: DocumentItem; onSaved: (d: DocumentItem) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const fileId = await uploadFile("documents", doc.id, file);
      onSaved(await api<DocumentItem>(`/documents/${doc.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ file_id: fileId, note }),
      }));
      setFile(null);
      setNote("");
      (e.target as HTMLFormElement).reset();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>Upload version {doc.versions.length + 1}</h2>
      <form className="stack-form" onSubmit={submit}>
        <Field label="File"><input type="file" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></Field>
        <Field label="What changed" hint="Optional — your supervisor sees this with the file.">
          <input maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || !file}>{busy ? "Uploading…" : "Upload version"}</Button>
      </form>
    </Card>
  );
}

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const { data: doc, error, setData } = useFetch<DocumentItem>(`/documents/${id}`);
  const [openError, setOpenError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!doc) return null;

  async function open(fileId: string) {
    setOpenError(null);
    try {
      await openFile(fileId);
    } catch (e) {
      setOpenError(errorText(e));
    }
  }

  return (
    <>
      <PageHeader eyebrow={`${DOC_KIND_LABELS[doc.doc_kind]} · ${doc.scholar.name}`} title={doc.title} />
      <div className="doc-grid">
        <Card>
          <h2>Versions</h2>
          {doc.versions.length === 0 ? <p className="muted">No versions uploaded yet.</p> : (
            <ol className="history">
              {doc.versions.map((v) => (
                <li key={v.id}>
                  <strong>v{v.version_no}</strong>{" "}
                  <button type="button" className="file-name" onClick={() => open(v.file_id)}>{v.file_name}</button>
                  <time dateTime={v.created_at}>{new Date(v.created_at).toLocaleString()}</time>
                  {v.note && <blockquote>{v.note}</blockquote>}
                </li>
              ))}
            </ol>
          )}
          <ErrorText>{openError}</ErrorText>
        </Card>
        {doc.can_edit && <NewVersion doc={doc} onSaved={setData} />}
      </div>
      <Comments target="documents" recordId={doc.id} />
      <p className="doc-back"><Link href="/documents">← All documents</Link></p>
    </>
  );
}
