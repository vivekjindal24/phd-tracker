"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { Ledger } from "@/components/Ledger";
import { ScholarSearch } from "@/components/ScholarSearch";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { PROJECT_STATUS_LABELS } from "@/lib/types";
import type { Project, ProjectStatus, Scholar, UtilisationCertificate } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function Members({ p, onChange }: { p: Project; onChange: (p: Project) => void }) {
  const [scholar, setScholar] = useState<Scholar | null>(null);
  const [role, setRole] = useState("Research scholar");
  const [error, setError] = useState<string | null>(null);

  async function call(path: string, init: RequestInit) {
    setError(null);
    try {
      onChange(await api<Project>(path, init));
      setScholar(null);
    } catch (err) {
      setError(errorText(err));
    }
  }

  function add(e: FormEvent) {
    e.preventDefault();
    if (scholar) call(`/projects/${p.id}/members`, { method: "POST", body: JSON.stringify({ scholar_id: scholar.id, member_role: role }) });
  }

  return (
    <Card>
      <h2>Members</h2>
      {p.members.length === 0 ? <p className="muted">No scholars on this project yet.</p> : (
        <ul className="plain-list">
          {p.members.map((m) => (
            <li key={m.id}>
              {m.scholar.name} <span className="muted">· {m.roll_number} · {m.member_role}</span>
              {p.can_manage && <Button kind="ghost" aria-label={`Remove ${m.scholar.name}`} onClick={() => call(`/projects/${p.id}/members/${m.id}`, { method: "DELETE" })}>Remove</Button>}
            </li>
          ))}
        </ul>
      )}
      {p.can_manage && (scholar ? (
        <form className="row" onSubmit={add}>
          <p>Add <strong>{scholar.full_name}</strong> as</p>
          <Field label="Role"><input required maxLength={200} value={role} onChange={(e) => setRole(e.target.value)} /></Field>
          <Button kind="secondary" type="submit">Add member</Button>
          <Button kind="ghost" onClick={() => setScholar(null)}>Cancel</Button>
        </form>
      ) : <ScholarSearch label="Add a scholar" onPick={setScholar} />)}
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

function Certificates({ p }: { p: Project }) {
  const { data, error, reload } = useFetch<UtilisationCertificate[]>(`/projects/${p.id}/ucs`);
  const [period, setPeriod] = useState({ period_start: "", period_end: "" });
  const [actError, setActError] = useState<string | null>(null);

  async function call(path: string, init: RequestInit) {
    setActError(null);
    try {
      await api(path, init);
      reload();
    } catch (err) {
      setActError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Utilisation certificates</h2>
      <ErrorText>{error}</ErrorText>
      {data?.length === 0 && <p className="muted">None recorded yet.</p>}
      {data?.map((uc) => (
        <section key={uc.id} className="uc">
          <h3>{formatDate(uc.period_start)} – {formatDate(uc.period_end)}</h3>
          {p.can_manage ? (
            <Field label="Submitted to the agency on">
              <input type="date" value={uc.submitted_on ?? ""}
                onChange={(e) => call(`/ucs/${uc.id}`, { method: "PATCH", body: JSON.stringify({ submitted_on: e.target.value || null }) })} />
            </Field>
          ) : <p className="muted">{uc.submitted_on ? `Submitted ${formatDate(uc.submitted_on)}` : "Not submitted yet"}</p>}
          <Attachments table="utilisation_certificates" recordId={uc.id} canUpload={p.can_manage} title="Signed certificate" />
        </section>
      ))}
      {p.can_manage && (
        <form className="row" onSubmit={(e) => { e.preventDefault(); call(`/projects/${p.id}/ucs`, { method: "POST", body: JSON.stringify(period) }); }}>
          <Field label="Period from"><input type="date" required value={period.period_start} onChange={(e) => setPeriod((v) => ({ ...v, period_start: e.target.value }))} /></Field>
          <Field label="Period to"><input type="date" required value={period.period_end} onChange={(e) => setPeriod((v) => ({ ...v, period_end: e.target.value }))} /></Field>
          <Button kind="secondary" type="submit">Add certificate</Button>
        </form>
      )}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { data: p, error, setData } = useFetch<Project>(`/projects/${id}`);
  const [statusError, setStatusError] = useState<string | null>(null);

  async function setStatus(status: ProjectStatus) {
    setStatusError(null);
    try {
      setData(await api<Project>(`/projects/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }));
    } catch (err) {
      setStatusError(errorText(err));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!p) return null;
  return (
    <>
      <PageHeader eyebrow={`Research project · ${p.agency}`} title={p.title} actions={<Link href="/projects">← All projects</Link>} />
      <Card>
        <dl className="kv">
          <dt>Principal investigator</dt><dd>{p.pi.name}</dd>
          <dt>Department</dt><dd>{p.unit.name}</dd>
          <dt>Sanction number</dt><dd className="mono">{p.sanction_number}</dd>
          <dt>Amount sanctioned</dt><dd className="mono">{formatMoney(p.amount_sanctioned)}</dd>
          <dt>Period</dt><dd>{formatDate(p.start_date)} – {formatDate(p.end_date)}</dd>
          <dt>Status</dt>
          <dd>
            {p.can_manage ? (
              <select aria-label="Project status" value={p.status} onChange={(e) => setStatus(e.target.value as ProjectStatus)}>
                {(Object.keys(PROJECT_STATUS_LABELS) as ProjectStatus[]).map((s) => <option key={s} value={s}>{PROJECT_STATUS_LABELS[s]}</option>)}
              </select>
            ) : PROJECT_STATUS_LABELS[p.status]}
          </dd>
        </dl>
        <ErrorText>{statusError}</ErrorText>
      </Card>
      <Members p={p} onChange={setData} />
      {p.sees_ledger && (
        <>
          <Card><h2>Ledger</h2><Ledger owner={{ project_id: p.id }} /></Card>
          <Certificates p={p} />
        </>
      )}
    </>
  );
}
