"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ETHICS_KIND_LABELS } from "@/lib/types";
import type { EthicsKind, EthicsRecord, EthicsView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const KINDS = Object.keys(ETHICS_KIND_LABELS) as EthicsKind[];

function AddRecord({ scholarId, onSaved }: { scholarId: string; onSaved: (v: EthicsView) => void }) {
  const [kind, setKind] = useState<EthicsKind>("human");
  const [committee, setCommittee] = useState("");
  const [number, setNumber] = useState("");
  const [approved, setApproved] = useState("");
  const [until, setUntil] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const none = kind === "not_required";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const body = none
      ? { kind, notes }
      : { kind, committee: committee || null, approval_number: number, approved_on: approved, valid_until: until || null, notes };
    try {
      onSaved(await api<EthicsView>(`/scholars/${scholarId}/ethics`, { method: "POST", body: JSON.stringify(body) }));
      setCommittee(""); setNumber(""); setApproved(""); setUntil(""); setNotes("");
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>Record ethics clearance</h3>
      <div className="row">
        <Field label="Kind">
          <select value={kind} onChange={(e) => setKind(e.target.value as EthicsKind)}>
            {KINDS.map((k) => <option key={k} value={k}>{ETHICS_KIND_LABELS[k]}</option>)}
          </select>
        </Field>
        {!none && (
          <>
            <Field label="Committee"><input maxLength={200} value={committee} onChange={(e) => setCommittee(e.target.value)} /></Field>
            <Field label="Approval number"><input required maxLength={100} value={number} onChange={(e) => setNumber(e.target.value)} /></Field>
            <Field label="Approved on"><input type="date" required value={approved} onChange={(e) => setApproved(e.target.value)} /></Field>
            <Field label="Valid until"><input type="date" min={approved} value={until} onChange={(e) => setUntil(e.target.value)} /></Field>
          </>
        )}
      </div>
      <Field label={none ? "Why none is required" : "Notes"} hint={none ? "For example: theoretical work, no human or animal subjects." : undefined}>
        <input required={none} maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit">Record</Button>
    </form>
  );
}

function lapsed(r: EthicsRecord): boolean {
  return r.valid_until !== null && r.valid_until < new Date().toISOString().slice(0, 10);
}

/** Ethics clearance for one scholar; a university setting can make the thesis wait for it. */
export function EthicsCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<EthicsView>(`/scholars/${scholarId}/ethics`);
  const [actError, setActError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;

  async function remove(id: string) {
    setActError(null);
    try {
      setData(await api<EthicsView>(`/ethics-clearances/${id}`, { method: "DELETE" }));
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <Card className="coursework">
      <h2>Research ethics{" "}
        <span className={`badge ${v.satisfied ? "badge-approved" : v.required ? "badge-sent_back" : "badge-draft"}`}>
          {v.satisfied ? "Recorded" : v.required ? "Needed before the thesis" : "Not recorded"}
        </span>
      </h2>
      {v.records.length === 0 && <p className="muted">Nothing recorded yet.</p>}
      <ul className="plain-list">
        {v.records.map((r) => (
          <li key={r.id}>
            <strong>{ETHICS_KIND_LABELS[r.kind]}</strong>
            {r.kind === "not_required" ? <> · {r.notes}</> : (
              <>
                {" "}· {r.approval_number}{r.committee && ` · ${r.committee}`} · approved {formatDate(r.approved_on!)}
                {r.valid_until && <> · valid until {formatDate(r.valid_until)}</>}
                {lapsed(r) && <> <span className="badge badge-sent_back">Lapsed</span></>}
                {r.notes && <span className="muted"> · {r.notes}</span>}
              </>
            )}
            {v.can_manage && <Button kind="ghost" onClick={() => remove(r.id)}>Remove</Button>}
            {r.kind !== "not_required" && (
              <Attachments table="ethics_clearances" recordId={r.id} canUpload={v.can_manage} title="Certificate" />
            )}
          </li>
        ))}
      </ul>
      {v.can_manage && <AddRecord scholarId={scholarId} onSaved={setData} />}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
