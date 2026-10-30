"use client";

import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Attachments } from "@/components/Attachments";
import { Celebrate, firstTime } from "@/components/Celebrate";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { RECOMMENDATION_LABELS, VIVA_LABELS } from "@/lib/types";
import type { Evaluation, Recommendation, VivaOutcome } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function RecordForm({ label, onSubmit, children }: { label: string; onSubmit: () => Promise<void>; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit();
      setOpen(false);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!open) return <Button kind="secondary" onClick={() => setOpen(true)}>{label}</Button>;
  return (
    <form className="verify" onSubmit={submit}>
      {children}
      <ErrorText>{error}</ErrorText>
      <div className="row">
        <Button kind="primary" type="submit" disabled={busy}>Save</Button>
        <Button kind="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}

function ReportForm({ thesisId, onSaved }: { thesisId: string; onSaved: (e: Evaluation) => void }) {
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [received, setReceived] = useState("");
  const [rec, setRec] = useState<Recommendation>("accept");
  return (
    <RecordForm label="Add examiner report" onSubmit={async () => {
      onSaved(await api<Evaluation>(`/theses/${thesisId}/examiner-reports`, {
        method: "POST",
        body: JSON.stringify({ examiner_name: name, institution, received_on: received, recommendation: rec }),
      }));
    }}>
      <div className="row">
        <Field label="Examiner"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <Field label="Institution"><input maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
      </div>
      <div className="row">
        <Field label="Received on"><input type="date" required value={received} onChange={(e) => setReceived(e.target.value)} /></Field>
        <Field label="Recommendation">
          <select value={rec} onChange={(e) => setRec(e.target.value as Recommendation)}>
            {(Object.keys(RECOMMENDATION_LABELS) as Recommendation[]).map((k) => <option key={k} value={k}>{RECOMMENDATION_LABELS[k]}</option>)}
          </select>
        </Field>
      </div>
    </RecordForm>
  );
}

function VivaForm({ thesisId, onSaved }: { thesisId: string; onSaved: (e: Evaluation) => void }) {
  const [held, setHeld] = useState("");
  const [venue, setVenue] = useState("");
  const [panel, setPanel] = useState("");
  const [outcome, setOutcome] = useState<VivaOutcome>("pass");
  return (
    <RecordForm label="Record viva" onSubmit={async () => {
      onSaved(await api<Evaluation>(`/theses/${thesisId}/vivas`, {
        method: "POST",
        body: JSON.stringify({ held_on: held, venue, panel, outcome }),
      }));
    }}>
      <div className="row">
        <Field label="Held on"><input type="date" required value={held} onChange={(e) => setHeld(e.target.value)} /></Field>
        <Field label="Outcome">
          <select value={outcome} onChange={(e) => setOutcome(e.target.value as VivaOutcome)}>
            {(Object.keys(VIVA_LABELS) as VivaOutcome[]).map((k) => <option key={k} value={k}>{VIVA_LABELS[k]}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Venue or link"><input maxLength={500} value={venue} onChange={(e) => setVenue(e.target.value)} /></Field>
      <Field label="Panel"><textarea maxLength={2000} value={panel} onChange={(e) => setPanel(e.target.value)} /></Field>
    </RecordForm>
  );
}

function DepositForm({ thesisId, onSaved }: { thesisId: string; onSaved: (e: Evaluation) => void }) {
  const [on, setOn] = useState("");
  const [url, setUrl] = useState("");
  return (
    <RecordForm label="Record Shodhganga deposit" onSubmit={async () => {
      onSaved(await api<Evaluation>(`/theses/${thesisId}/deposit`, {
        method: "PUT",
        body: JSON.stringify({ deposited_on: on, handle_url: url }),
      }));
    }}>
      <div className="row">
        <Field label="Deposited on"><input type="date" required value={on} onChange={(e) => setOn(e.target.value)} /></Field>
        <Field label="Shodhganga handle / URL"><input type="url" required value={url} onChange={(e) => setUrl(e.target.value)} /></Field>
      </div>
    </RecordForm>
  );
}

/** The furthest milestone worth celebrating: the Shodhganga deposit, else a passed viva. */
function milestone(ev: Evaluation): { key: string; text: string } | null {
  if (ev.deposit) return { key: "deposit", text: "Deposited in Shodhganga! 📚" };
  if (ev.vivas.some((v) => v.outcome === "pass")) return { key: "viva", text: "Viva passed! 🎓" };
  return null;
}

/** Everything after the thesis is approved (PRD M3). The API hides what this viewer may not
 *  see yet — unreleased reports, examiner names before the viva. */
export function ThesisEvaluation({ thesisId, isOwn }: { thesisId: string; isOwn: boolean }) {
  const { data: ev, error, setData } = useFetch<Evaluation>(`/theses/${thesisId}/evaluation`);
  const [actError, setActError] = useState<string | null>(null);
  const [celebrate, setCelebrate] = useState<string | null>(null);

  // The scholar celebrates each milestone once, the first time they see it.
  useEffect(() => {
    if (!ev || !isOwn) return;
    const msg = milestone(ev);
    if (msg && firstTime(`${msg.key}.${thesisId}`)) setCelebrate(msg.text);
  }, [ev, isOwn, thesisId]);

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!ev) return null;

  async function release() {
    setActError(null);
    try {
      setData(await api<Evaluation>(`/theses/${thesisId}/release-reports`, { method: "POST" }));
    } catch (e) {
      setActError(errorText(e));
    }
  }

  // The office recording a passed viva or the deposit celebrates once the API confirms it.
  const recorded = (next: Evaluation) => {
    const before = milestone(ev)?.key;
    setData(next);
    const msg = milestone(next);
    if (msg && msg.key !== before) setCelebrate(msg.text);
  };

  const safeUrl = (u: string) => (/^https?:\/\//.test(u) ? u : undefined);
  return (
    <Card className="evaluation">
      {celebrate && <Celebrate message={celebrate} onDone={() => setCelebrate(null)} />}
      <h2>Evaluation</h2>
      <h3>Examiner reports</h3>
      {ev.names_hidden && <p className="muted">Examiner names stay confidential until the viva.</p>}
      {ev.reports.length === 0 ? <p className="muted">No reports to show yet.</p> : (
        <ul className="plain-list">
          {ev.reports.map((r) => (
            <li key={r.id}>
              <strong>{r.examiner_name ?? "Examiner"}</strong>{r.institution && ` · ${r.institution}`}
              {" · "}{RECOMMENDATION_LABELS[r.recommendation]} · received {formatDate(r.received_on)}
              {!r.released && <span className="badge badge-draft">Not released</span>}
              <Attachments table="examiner_reports" recordId={r.id} canUpload={ev.can_record_reports} title="Report file" />
            </li>
          ))}
        </ul>
      )}
      {ev.can_record_reports && (
        <div className="row">
          <ReportForm thesisId={thesisId} onSaved={setData} />
          {ev.unreleased_count > 0 && (
            <Button kind="primary" onClick={release}>Release {ev.unreleased_count} report{ev.unreleased_count === 1 ? "" : "s"} to the scholar</Button>
          )}
        </div>
      )}
      <h3>Viva</h3>
      {ev.vivas.length === 0 ? <p className="muted">Not held yet.</p> : (
        <ul className="plain-list">
          {ev.vivas.map((v) => (
            <li key={v.id}>
              <strong>{VIVA_LABELS[v.outcome]}</strong> · {formatDate(v.held_on)}{v.venue && ` · ${v.venue}`}
              {v.panel && <div className="muted">Panel: {v.panel}</div>}
              <Attachments table="vivas" recordId={v.id} canUpload={ev.can_record_viva} title="Viva report" />
            </li>
          ))}
        </ul>
      )}
      {ev.can_record_viva && <VivaForm thesisId={thesisId} onSaved={recorded} />}
      <h3>Shodhganga deposit</h3>
      {ev.deposit ? (
        <>
          <p>Deposited {formatDate(ev.deposit.deposited_on)} ·{" "}
            <a href={safeUrl(ev.deposit.handle_url)} target="_blank" rel="noopener noreferrer">{ev.deposit.handle_url}</a></p>
          <Attachments table="shodhganga_deposits" recordId={ev.deposit.id} canUpload={ev.can_record_deposit} title="Deposit certificate" />
        </>
      ) : <p className="muted">Not deposited yet.</p>}
      {ev.can_record_deposit && <DepositForm thesisId={thesisId} onSaved={recorded} />}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
