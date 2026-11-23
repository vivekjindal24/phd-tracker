"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Attachments } from "@/components/Attachments";
import { PatentForm } from "@/components/items/PatentForm";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { PATENT_CHECK_LABELS, PATENT_STATUS_LABELS, PATENT_VERIFIER_LABELS, VERIFICATION_BADGE } from "@/lib/types";
import type { Patent } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

/** The chosen office's check (PRD M10): verify against the patent office's record, or return
 *  it with a note saying what to correct. */
function OfficeCheck({ p, onSaved }: { p: Patent; onSaved: (v: Patent) => void }) {
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(step: "verify" | "return", body: object) {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<Patent>(`/patents/${p.id}/${step}`, { method: "POST", body: JSON.stringify(body) }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>Check</h2>
      {p.verification === "waiting" && (
        <div className="stack-form">
          <p className="muted">Check the application number, dates and status against the patent office&apos;s record (for India, IP India&apos;s public search), then verify. Only verified patents count in the NAAC data.</p>
          <div><Button kind="primary" disabled={busy} onClick={() => send("verify", {})}>Verify</Button></div>
        </div>
      )}
      {p.verification !== "returned" ? (
        <div className="stack-form">
          <Field label={p.verification === "verified" ? "Return it for a correction" : "Or return it to the inventor"}
            hint="Say what to correct; they are told, and it comes back to you once changed.">
            <textarea rows={2} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <div><Button kind="secondary" disabled={busy || !note.trim()} onClick={() => send("return", { note })}>Return</Button></div>
        </div>
      ) : <p className="muted">Returned to the inventor. It comes back here once they correct it.</p>}
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

export default function PatentPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { data: p, error, setData } = useFetch<Patent>(`/patents/${id}`);
  const [editing, setEditing] = useState(false);
  const [actError, setActError] = useState<string | null>(null);

  async function remove() {
    setActError(null);
    try {
      await api(`/patents/${id}`, { method: "DELETE" });
      router.push("/patents");
    } catch (e) {
      setActError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!p) return null;
  const by = `${p.checked_by ? ` by ${p.checked_by}` : ""}${p.checked_at ? ` on ${formatDate(p.checked_at)}` : ""}`;
  const office = `the ${PATENT_VERIFIER_LABELS[p.verifier]}`;
  return (
    <>
      <PageHeader eyebrow={`Patent · ${p.owner.name}`} title={p.title}
        actions={<span className={`badge ${VERIFICATION_BADGE[p.verification]}`}>{PATENT_CHECK_LABELS[p.verification]}{p.verification === "verified" ? by : ""}</span>} />
      {p.verification === "returned" && p.return_note && (
        <Card className="tile-butter">
          <h2>Returned{p.checked_at ? ` on ${formatDate(p.checked_at)}` : ""}</h2>
          <p>{p.return_note}</p>
          {p.can_edit && <p className="muted">Correct it below; saving sends it back to {office}.</p>}
        </Card>
      )}
      {editing ? (
        <Card>
          <h2>Update patent</h2>
          {p.verification === "verified" && <p className="muted">Saving sends it back to {office} to check again.</p>}
          <PatentForm initial={p} submitLabel={p.verification === "waiting" ? "Save" : "Save and send to be checked"}
            onCancel={() => setEditing(false)}
            onSubmit={async (value) => {
              setData(await api<Patent>(`/patents/${p.id}`, { method: "PUT", body: JSON.stringify(value) }));
              setEditing(false);
            }} />
        </Card>
      ) : (
        <Card>
          <h2>Patent</h2>
          <dl className="kv">
            <dt>Inventors</dt><dd>{p.inventors}</dd>
            <dt>Application</dt><dd><span className="mono">{p.application_number}</span> · filed {formatDate(p.filed_on)} · {p.office}</dd>
            <dt>Status</dt>
            <dd>
              {PATENT_STATUS_LABELS[p.patent_status]}
              {p.published_on && <> · published {formatDate(p.published_on)}</>}
              {p.granted_on && <> · granted {formatDate(p.granted_on)}</>}
            </dd>
            {p.patent_number && <><dt>Patent number</dt><dd className="mono">{p.patent_number}</dd></>}
            <dt>{p.owner_kind === "scholar" ? "Scholar" : "Faculty"}</dt><dd>{p.owner.name} · {p.unit}</dd>
            <dt>Checked by</dt><dd>The {PATENT_VERIFIER_LABELS[p.verifier]}</dd>
          </dl>
          {p.can_edit && (
            <div className="row">
              <Button onClick={() => setEditing(true)}>{p.verification === "verified" ? "Update (e.g. it was granted)" : "Edit details"}</Button>
              {p.verification !== "verified" && <Button kind="ghost" onClick={remove}>Remove</Button>}
            </div>
          )}
          <ErrorText>{actError}</ErrorText>
        </Card>
      )}
      <Attachments table="patents" recordId={p.id} canUpload={p.can_edit && p.verification !== "verified"} title="Papers"
        hint="The filing receipt, the publication in the journal or the grant certificate (optional)." />
      {p.can_check && <OfficeCheck key={p.verification} p={p} onSaved={setData} />}
    </>
  );
}
