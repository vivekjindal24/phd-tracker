"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { DOC_KIND_LABELS } from "@/lib/types";
import type { DocKind, DocumentItem } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function NewDocument() {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<DocKind>("chapter");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const doc = await api<DocumentItem>("/documents", { method: "POST", body: JSON.stringify({ title, doc_kind: kind }) });
      router.push(`/documents/${doc.id}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>New document</h2>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          <Field label="Title"><input required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
          <Field label="Kind">
            <select value={kind} onChange={(e) => setKind(e.target.value as DocKind)}>
              {(Object.keys(DOC_KIND_LABELS) as DocKind[]).map((k) => <option key={k} value={k}>{DOC_KIND_LABELS[k]}</option>)}
            </select>
          </Field>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Create</Button>
      </form>
    </Card>
  );
}

export default function DocumentsPage() {
  const { me } = useSession();
  const { data, error } = useFetch<DocumentItem[]>("/documents");
  return (
    <>
      <PageHeader eyebrow="Documents & thesis" title="Drafts & chapters" />
      <p className="muted">Only the scholar and their supervisor see these. Every upload is kept as a numbered version.</p>
      {me?.scholar_id && <NewDocument />}
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Documents" head={["Document", "Scholar", "Kind", "Versions", "Last change"]}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No documents yet</h2></div>}>
          {data.map((d) => (
            <tr key={d.id}>
              <td><Link href={`/documents/${d.id}`}>{d.title}</Link></td>
              <td>{d.scholar.name}</td>
              <td>{DOC_KIND_LABELS[d.doc_kind]}</td>
              <td className="mono">{d.versions.length}</td>
              <td className="mono">{new Date(d.updated_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
