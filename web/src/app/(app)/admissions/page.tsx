"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { ENTRANCE_LABELS, RESULT_LABELS } from "@/lib/types";
import type { Admission, EntranceRoute, InterviewResult, OrgUnit } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function AddCandidate({ units, onAdded }: { units: OrgUnit[]; onAdded: () => void }) {
  const [v, setV] = useState({ candidate_name: "", email: "", phone: "", unit_id: "", entrance_route: "net_jrf" as EntranceRoute, entrance_score: "", interview_date: "", admitted_on: "" });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v, value: string) => setV((p) => ({ ...p, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/admissions", {
        method: "POST",
        body: JSON.stringify({
          ...v,
          phone: v.phone || null,
          entrance_score: v.entrance_score === "" ? null : Number(v.entrance_score),
          interview_date: v.interview_date || null,
          admitted_on: v.admitted_on || null,
        }),
      });
      setV((p) => ({ ...p, candidate_name: "", email: "", phone: "", entrance_score: "" }));
      onAdded();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Record a candidate</h2>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          <Field label="Name"><input required maxLength={200} value={v.candidate_name} onChange={(e) => set("candidate_name", e.target.value)} /></Field>
          <Field label="Email"><input type="email" required value={v.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Phone"><input maxLength={20} value={v.phone} onChange={(e) => set("phone", e.target.value)} /></Field>
        </div>
        <div className="row">
          <Field label="Department">
            <select required value={v.unit_id} onChange={(e) => set("unit_id", e.target.value)}>
              <option value="" disabled>Choose…</option>
              {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </Field>
          <Field label="Entrance route">
            <select value={v.entrance_route} onChange={(e) => set("entrance_route", e.target.value)}>
              {(Object.keys(ENTRANCE_LABELS) as EntranceRoute[]).map((k) => <option key={k} value={k}>{ENTRANCE_LABELS[k]}</option>)}
            </select>
          </Field>
          <Field label="Score"><input type="number" min={0} step={0.01} value={v.entrance_score} onChange={(e) => set("entrance_score", e.target.value)} /></Field>
        </div>
        <div className="row">
          <Field label="Interview date"><input type="date" value={v.interview_date} onChange={(e) => set("interview_date", e.target.value)} /></Field>
          <Field label="Admitted on"><input type="date" value={v.admitted_on} onChange={(e) => set("admitted_on", e.target.value)} /></Field>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Add candidate</Button>
      </form>
    </Card>
  );
}

function Convert({ a, onDone }: { a: Admission; onDone: () => void }) {
  const [roll, setRoll] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/admissions/${a.id}/convert`, { method: "POST", body: JSON.stringify({ roll_number: roll }) });
      onDone();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="row" onSubmit={submit}>
      <input aria-label={`Roll number for ${a.candidate_name}`} required maxLength={50} placeholder="Roll number"
        value={roll} onChange={(e) => setRoll(e.target.value)} />
      <Button kind="primary" type="submit" disabled={busy}>{busy ? "Creating…" : "Make scholar"}</Button>
      <ErrorText>{error}</ErrorText>
    </form>
  );
}

function ResultSelect({ a, onSaved }: { a: Admission; onSaved: () => void }) {
  const [error, setError] = useState<string | null>(null);
  async function change(value: InterviewResult) {
    setError(null);
    try {
      await api(`/admissions/${a.id}`, { method: "PATCH", body: JSON.stringify({ interview_result: value }) });
      onSaved();
    } catch (e) {
      setError(errorText(e));
    }
  }
  return (
    <>
      <select aria-label={`Result for ${a.candidate_name}`} value={a.interview_result} onChange={(e) => change(e.target.value as InterviewResult)}>
        {(Object.keys(RESULT_LABELS) as InterviewResult[]).map((k) => <option key={k} value={k}>{RESULT_LABELS[k]}</option>)}
      </select>
      <ErrorText>{error}</ErrorText>
    </>
  );
}

export default function AdmissionsPage() {
  const { me } = useSession();
  const { data, error, reload } = useFetch<Admission[]>("/admissions");
  const { data: units } = useFetch<OrgUnit[]>("/org-units");
  const isOffice = me?.office_roles.includes("research_office") ?? false;
  const adminPaths = me?.unit_roles.filter((r) => r.role === "admin").map((r) => r.unit_path) ?? [];
  const writable = (units ?? []).filter((u) => isOffice || adminPaths.some((p) => u.path === p || u.path.startsWith(`${p}.`)));

  return (
    <>
      <PageHeader eyebrow="Academic administration" title="Admissions" />
      <p className="muted">An internal record of admitted candidates. A selected candidate becomes a scholar with a login; they get an email to set their password.</p>
      {writable.length > 0 && <AddCandidate units={writable} onAdded={reload} />}
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Admissions" head={["Candidate", "Department", "Route", "Interview", "Result", ""]}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No candidates yet</h2></div>}>
          {data.map((a) => (
            <tr key={a.id}>
              <td>{a.candidate_name}<div className="muted">{a.email}</div></td>
              <td>{a.unit.name}</td>
              <td>{ENTRANCE_LABELS[a.entrance_route]}{a.entrance_score !== null && <span className="muted"> · {a.entrance_score}</span>}</td>
              <td className="mono">{a.interview_date ? formatDate(a.interview_date) : "—"}</td>
              <td>{a.can_edit && !a.scholar_id ? <ResultSelect a={a} onSaved={reload} /> : RESULT_LABELS[a.interview_result]}</td>
              <td>
                {a.scholar_id ? <Link href={`/scholars/${a.scholar_id}`}>Scholar profile →</Link>
                  : a.can_edit && a.interview_result === "selected" ? <Convert a={a} onDone={reload} /> : null}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
