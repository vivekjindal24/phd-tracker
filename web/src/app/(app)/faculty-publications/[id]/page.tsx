"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { PaperFile } from "@/components/items/PaperFile";
import { IndexingChecks, PublicationForm } from "@/components/items/PublicationForm";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import {
  INDEXING_LABELS,
  PUB_STATUS_LABELS,
  PUB_TYPE_LABELS,
  VERIFICATION_BADGE,
  VERIFICATION_LABELS,
} from "@/lib/types";
import type { FacultyPublication, Indexing } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const BASE = "/faculty-publications";

function safeDoiUrl(doi: string): string {
  return `https://doi.org/${encodeURIComponent(doi).replace(/%2F/g, "/")}`;
}

/** The Library's check (PRD M1): correct indexing and DOI and verify, or return with a note. */
function LibraryCheck({ p, onSaved }: { p: FacultyPublication; onSaved: (v: FacultyPublication) => void }) {
  const [indexing, setIndexing] = useState<Indexing[]>(p.indexing);
  const [doi, setDoi] = useState(p.doi ?? "");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(step: "verify" | "return", body: object) {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<FacultyPublication>(`${BASE}/${p.id}/${step}`, { method: "POST", body: JSON.stringify(body) }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>Library verification</h2>
      {p.verification === "waiting" && (
        <div className="stack-form">
          <p className="muted">Correct the indexing and DOI to what you checked (Scopus / Web of Science / UGC-CARE list), then verify. Only verified papers count in the NAAC data.</p>
          <IndexingChecks value={indexing} onChange={setIndexing} />
          <Field label="DOI">
            <input value={doi} maxLength={210} pattern="10\.\d{4,9}/\S+" onChange={(e) => setDoi(e.target.value)} />
          </Field>
          <div><Button kind="primary" disabled={busy} onClick={() => send("verify", { indexing, doi: doi || null })}>Verify</Button></div>
        </div>
      )}
      {p.verification !== "returned" && (
        <div className="stack-form">
          <Field label={p.verification === "verified" ? "Return it for a correction" : "Or return it to the author"}
            hint="Say what to correct; they are told, and it comes back to you once changed.">
            <textarea rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div><Button kind="secondary" disabled={busy || !note.trim()} onClick={() => send("return", { note })}>Return</Button></div>
        </div>
      )}
      {p.verification === "returned" && <p className="muted">Returned to the author. It comes back here once they correct it.</p>}
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

export default function FacultyPublicationPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: p, error, setData } = useFetch<FacultyPublication>(`${BASE}/${id}`);
  const [editing, setEditing] = useState(false);
  const [actError, setActError] = useState<string | null>(null);

  async function remove() {
    setActError(null);
    try {
      await api(`${BASE}/${id}`, { method: "DELETE" });
      router.push(BASE);
    } catch (e) {
      setActError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!p) return null;
  // "by Fatima Sheikh on 23 Nov 2026": who in the Library checked it last, and when.
  const checked = `${p.checked_by ? ` by ${p.checked_by}` : ""}${p.checked_at ? ` on ${formatDate(p.checked_at)}` : ""}`;
  return (
    <>
      <PageHeader eyebrow={`Faculty publication · ${p.faculty.name}`} title={p.title}
        actions={<span className={`badge ${VERIFICATION_BADGE[p.verification]}`}>{VERIFICATION_LABELS[p.verification]}{p.verification === "verified" ? checked : ""}</span>} />
      {p.verification === "returned" && p.return_note && (
        <Card className="tile-butter">
          <h2>Returned by the Library{p.checked_at ? ` on ${formatDate(p.checked_at)}` : ""}</h2>
          <p>{p.return_note}</p>
          {p.can_edit && <p className="muted">Correct it below; saving sends it back to the Library.</p>}
        </Card>
      )}
      {editing ? (
        <Card>
          <h2>Edit publication</h2>
          <PublicationForm base={BASE} initial={p} submitLabel={p.verification === "returned" ? "Save and send back" : "Save"}
            onCancel={() => setEditing(false)}
            onSubmit={async (value) => {
              setData(await api<FacultyPublication>(`${BASE}/${p.id}`, { method: "PATCH", body: JSON.stringify(value) }));
              setEditing(false);
            }} />
        </Card>
      ) : (
        <Card>
          <h2>Publication</h2>
          <dl className="kv">
            <dt>Authors</dt><dd>{p.authors}</dd>
            <dt>Type</dt><dd>{PUB_TYPE_LABELS[p.pub_type]} · {PUB_STATUS_LABELS[p.pub_status]} · {p.pub_year}</dd>
            <dt>Venue</dt><dd>{p.venue}{p.issn_isbn && <span className="muted"> · {p.issn_isbn}</span>}</dd>
            <dt>Indexed in</dt>
            <dd>{p.indexing.length ? p.indexing.map((i) => INDEXING_LABELS[i]).join(", ") : <span className="muted">Not indexed</span>}</dd>
            <dt>DOI</dt>
            <dd>{p.doi ? <a href={safeDoiUrl(p.doi)} target="_blank" rel="noopener noreferrer">{p.doi}</a> : <span className="muted">None</span>}</dd>
            <dt>Department</dt><dd>{p.unit}</dd>
          </dl>
          {p.can_edit && (
            <div className="row">
              <Button onClick={() => setEditing(true)}>Edit details</Button>
              <Button kind="ghost" onClick={remove}>Remove</Button>
            </div>
          )}
          <ErrorText>{actError}</ErrorText>
        </Card>
      )}
      <PaperFile table="faculty_publications" recordId={p.id} canUpload={p.can_edit} when="before the Library verifies it" />
      {p.can_check && <LibraryCheck key={p.verification} p={p} onSaved={setData} />}
    </>
  );
}
