"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { TIME_KIND_LABELS } from "@/lib/types";
import type { DurationStatus, DurationView, TimeKind } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const STATUS: Record<DurationStatus, [string, string]> = {
  ok: ["Within the limit", "badge badge-approved"],
  near: ["Nearing the limit", "badge badge-draft"],
  over: ["Past the limit", "badge badge-sent_back"],
  done: ["Thesis submitted", "badge badge-approved"],
  left: ["Left the programme", "badge"],
  unknown: ["Admission date missing", "badge badge-draft"],
};

function AddRecord({ scholarId, onSaved }: { scholarId: string; onSaved: (v: DurationView) => void }) {
  const [kind, setKind] = useState<TimeKind>("extension");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [resolution, setResolution] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await api<DurationView>(`/scholars/${scholarId}/time-adjustments`, {
        method: "POST",
        body: JSON.stringify({ kind, start_date: start, end_date: end, resolution_number: resolution || null }),
      }));
      setStart(""); setEnd(""); setResolution("");
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>Record an extension or leave</h3>
      <div className="row">
        <Field label="Kind">
          <select value={kind} onChange={(e) => setKind(e.target.value as TimeKind)}>
            {(Object.keys(TIME_KIND_LABELS) as TimeKind[]).map((k) => <option key={k} value={k}>{TIME_KIND_LABELS[k]}</option>)}
          </select>
        </Field>
        <Field label="From"><input type="date" required value={start} onChange={(e) => setStart(e.target.value)} /></Field>
        <Field label="To"><input type="date" required min={start} value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
      </div>
      <Field label="Resolution number" hint="The committee decision that approved it.">
        <input maxLength={100} value={resolution} onChange={(e) => setResolution(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit">Record</Button>
    </form>
  );
}

/** The UGC maximum duration for one scholar, warned about before it passes (PRD Phase 4). */
export function DurationCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<DurationView>(`/scholars/${scholarId}/duration`);
  const [actError, setActError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;
  const [label, badge] = STATUS[v.status];

  async function remove(id: string) {
    setActError(null);
    try {
      setData(await api<DurationView>(`/time-adjustments/${id}`, { method: "DELETE" }));
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <Card className="coursework">
      <h2>Time limit <span className={badge}>{label}</span></h2>
      <dl className="kv">
        <dt>Admitted</dt><dd>{v.admission_date ? formatDate(v.admission_date) : <span className="muted">Not recorded</span>}</dd>
        <dt>Must submit by</dt>
        <dd>{v.limit_date ? <>{formatDate(v.limit_date)}{v.days_left !== null && v.days_left >= 0 && v.status !== "done" && v.status !== "left" && <span className="muted"> · {v.days_left} days left</span>}</> : "—"}</dd>
        <dt>Includes</dt>
        <dd>{v.max_years} years{v.extension_days > 0 && ` + ${v.extension_days} days extension`}{v.relaxation_days > 0 && ` + ${v.relaxation_days} days relaxation`}</dd>
        {v.leave_days > 0 && (<><dt>Leave taken</dt><dd>{v.leave_days} days</dd></>)}
      </dl>
      {v.warnings.length > 0 && (
        <ul className="warn-list" aria-label="Duration warnings">{v.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
      )}
      {v.adjustments.length > 0 && (
        <ul className="plain-list">
          {v.adjustments.map((a) => (
            <li key={a.id}>
              <strong>{TIME_KIND_LABELS[a.kind]}</strong> · {formatDate(a.start_date)} – {formatDate(a.end_date)} ({a.days} days)
              {a.resolution_number && <span className="muted"> · {a.resolution_number}</span>}
              {v.can_manage && <Button kind="ghost" onClick={() => remove(a.id)}>Remove</Button>}
            </li>
          ))}
        </ul>
      )}
      {v.can_manage && <AddRecord scholarId={scholarId} onSaved={setData} />}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
