"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { DownloadButton } from "@/components/DownloadButton";
import { PersonPicker } from "@/components/PersonPicker";
import { MilestoneStatusBadge } from "@/components/MilestoneStatusBadge";
import { Button, ErrorText, Field, PageHeader, ShowMore, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { APPROVAL_BODIES, MILESTONE_LABELS, MILESTONE_STATUSES } from "@/lib/types";
import type { ApprovalBody, Milestone, MilestoneStatus, MilestoneType, Scholar } from "@/lib/types";
import { errorText, usePagedFetch } from "@/lib/useFetch";
import "./register.css";

function RecordDecision({ onSaved }: { onSaved: () => void }) {
  const [scholar, setScholar] = useState<Scholar | null>(null);
  const [type, setType] = useState<MilestoneType>("proposal_approval");
  const [status, setStatus] = useState<MilestoneStatus>("Approved");
  const [body, setBody] = useState<ApprovalBody>("RDC");
  const [number, setNumber] = useState("");
  const [date, setDate] = useState("");
  const [notes, setNotes] = useState("");
  const [typedTitle, setTypedTitle] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const isProposal = type === "proposal_approval";
  const title = typedTitle ?? scholar?.research_title ?? "";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/milestones", {
        method: "POST",
        body: JSON.stringify({
          scholar_id: scholar?.id, milestone_type: type, status, approval_body: body,
          resolution_number: number || null, resolution_date: date || null, notes,
          approved_title: isProposal && title.trim() ? title : null,
        }),
      });
      setNumber("");
      setNotes("");
      setTypedTitle(null);
      onSaved();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="clay card decision-form" onSubmit={submit}>
      <h2>Record a decision</h2>
      <PersonPicker label="Scholar" path="/scholars" value={scholar} onPick={setScholar}
        detail={(s) => `${s.roll_number} · ${s.unit.name}`} />
      <div className="three">
        <Field label="Milestone">
          <select value={type} onChange={(e) => setType(e.target.value as MilestoneType)}>
            {(Object.keys(MILESTONE_LABELS) as MilestoneType[]).map((k) => (
              <option key={k} value={k}>{MILESTONE_LABELS[k]}</option>
            ))}
          </select>
        </Field>
        <Field label="Decision">
          <select value={status} onChange={(e) => setStatus(e.target.value as MilestoneStatus)}>
            {MILESTONE_STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Committee">
          <select value={body} onChange={(e) => setBody(e.target.value as ApprovalBody)}>
            {APPROVAL_BODIES.map((b) => <option key={b}>{b}</option>)}
          </select>
        </Field>
      </div>
      <div className="three">
        <Field label="Resolution number">
          <input maxLength={100} value={number} onChange={(e) => setNumber(e.target.value)}
            placeholder="e.g. RDC/2026/14" />
        </Field>
        <Field label="Resolution date">
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </Field>
      </div>
      {isProposal && (
        <Field label="Approved title" hint="The thesis and certificate use this title. It starts from the scholar's research title.">
          <input maxLength={500} value={title} onChange={(e) => setTypedTitle(e.target.value)} />
        </Field>
      )}
      <Field label="Notes">
        <input maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="primary" type="submit">Record decision</Button>
    </form>
  );
}

/** The committee's title, editable by those who keep the register. Saving updates the thesis. */
function ApprovedTitle({ milestone, canEdit, onSaved }: { milestone: Milestone; canEdit: boolean; onSaved: () => void }) {
  const [title, setTitle] = useState(milestone.approved_title ?? "");
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/milestones/${milestone.id}`, { method: "PATCH", body: JSON.stringify({ approved_title: title }) });
      setEditing(false);
      onSaved();
    } catch (err) {
      setError(errorText(err));
    }
  }

  if (!editing) {
    return (
      <>
        <br /><span className="muted">{milestone.approved_title ?? "No approved title yet"}</span>
        {canEdit && <> <Button kind="ghost" onClick={() => setEditing(true)}>Edit title</Button></>}
      </>
    );
  }
  return (
    <form onSubmit={save}>
      <Field label="Approved title">
        <input required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit">Save title</Button>
    </form>
  );
}

export default function RegisterPage() {
  const { me } = useSession();
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [sort, setSort] = useState("");
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (type) params.set("milestone_type", type);
  if (sort) params.set("sort", sort);
  const { data, error, reload, hasMore, more, total } = usePagedFetch<Milestone>(`/milestones?${params}`, 200);
  const canRecord = me?.roles.some((r) => r === "admin" || r === "research_office") ?? false;

  return (
    <>
      <PageHeader eyebrow="Committee decisions" title="RDC register"
        actions={<>
          <DownloadButton path={`/register.pdf?${params}`}>Register PDF</DownloadButton>
          <DownloadButton path={`/register.csv?${params}`}>Register CSV</DownloadButton>
        </>} />
      <div className="register-grid">
        <div>
          <div className="toolbar">
            <Field label="Milestone">
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="">All</option>
                {(Object.keys(MILESTONE_LABELS) as MilestoneType[]).map((k) => (
                  <option key={k} value={k}>{MILESTONE_LABELS[k]}</option>
                ))}
              </select>
            </Field>
            <Field label="Decision">
              <select value={status} onChange={(e) => setStatus(e.target.value)}>
                <option value="">All</option>
                {MILESTONE_STATUSES.map((s) => <option key={s}>{s}</option>)}
              </select>
            </Field>
          </div>
          <ErrorText>{error}</ErrorText>
          {data && (
            <Table
              label="RDC register"
              head={["Scholar", "Milestone", "Committee", "Resolution", "Decision"]}
          sort={{ by: sort, keys: ["scholar", "milestone", "committee", "resolution", "decision"], onChange: setSort }}
              empty={<div className="empty-state"><Owl pose="empty" size={90} /><p>No decisions recorded yet.</p></div>}
            >
              {data.map((m) => (
                <tr key={m.id}>
                  <td>
                    <Link href={`/scholars/${m.scholar.id}`}>{m.scholar.name}</Link>
                    <br /><span className="mono">{m.roll_number}</span>
                  </td>
                  <td>
                    {MILESTONE_LABELS[m.milestone_type]}
                    {m.milestone_type === "proposal_approval" && <ApprovedTitle milestone={m} canEdit={canRecord} onSaved={reload} />}
                  </td>
                  <td>{m.approval_body}</td>
                  <td>
                    {m.resolution_number ?? <span className="muted">—</span>}
                    {m.resolution_date && <><br /><span className="mono">{formatDate(m.resolution_date)}</span></>}
                  </td>
                  <td><MilestoneStatusBadge status={m.status} /></td>
                </tr>
              ))}
            </Table>
          )}
          <ShowMore hasMore={hasMore} more={more} shown={data?.length} total={total} />
        </div>
        {canRecord && <RecordDecision onSaved={reload} />}
      </div>
    </>
  );
}
