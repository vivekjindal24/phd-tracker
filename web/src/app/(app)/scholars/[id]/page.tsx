"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { Comments } from "@/components/Comments";
import { CourseworkCard } from "@/components/CourseworkCard";
import { InviteButton } from "@/components/InviteButton";
import { MilestoneStatusBadge } from "@/components/MilestoneStatusBadge";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { MILESTONE_LABELS, STAGES } from "@/lib/types";
import type { Faculty, Milestone, Scholar, Stage } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./profile.css";

function AssignCard({
  scholar,
  kind,
  onSaved,
}: {
  scholar: Scholar;
  kind: "supervisor" | "co-supervisor";
  onSaved: (s: Scholar) => void;
}) {
  const current = kind === "supervisor" ? scholar.supervisor : scholar.co_supervisor;
  // Supervisors must have spare UGC capacity; co-supervisors can be anyone (even external).
  const { data: faculty } = useFetch<Faculty[]>(
    kind === "supervisor" ? "/faculty?can_supervise=true&with_capacity=true" : "/faculty",
  );
  const [choice, setChoice] = useState(current?.id ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => setChoice(current?.id ?? ""), [current?.id]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<Scholar>(`/scholars/${scholar.id}/${kind}`, {
        method: "PUT",
        body: JSON.stringify({ faculty_id: choice || null }),
      }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const options = faculty?.filter((f) => f.id !== current?.id) ?? [];
  return (
    <div className="assign">
      <Field label={kind === "supervisor" ? "Supervisor" : "Co-supervisor"}
        hint={kind === "supervisor" ? "Only supervisors below their UGC limit are listed." : undefined}>
        <select value={choice} onChange={(e) => setChoice(e.target.value)}>
          <option value="">— None —</option>
          {current && <option value={current.id}>{current.name} (current)</option>}
          {options.map((f) => (
            <option key={f.id} value={f.id}>
              {f.full_name} · {f.unit.name} ({f.load}/{f.max_scholars})
            </option>
          ))}
        </select>
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" disabled={busy || choice === (current?.id ?? "")} onClick={save}>
        Save {kind}
      </Button>
    </div>
  );
}

function Decisions({ scholarId }: { scholarId: string }) {
  const { data } = useFetch<Milestone[]>(`/milestones?scholar_id=${scholarId}`);
  if (!data) return null;
  return (
    <Card className="decisions">
      <h2>Committee decisions</h2>
      {data.length === 0 ? (
        <p className="muted">No decisions recorded yet.</p>
      ) : (
        <ul className="decision-list">
          {data.map((m) => (
            <li key={m.id}>
              <strong>{MILESTONE_LABELS[m.milestone_type]}</strong> · {m.approval_body}
              {m.resolution_number && ` · ${m.resolution_number}`}
              {m.resolution_date && ` · ${formatDate(m.resolution_date)}`}
              <MilestoneStatusBadge status={m.status} />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function ScholarProfile() {
  const { id } = useParams<{ id: string }>();
  const { me } = useSession();
  const { data: scholar, error, setData } = useFetch<Scholar>(`/scholars/${id}`);
  const [stage, setStage] = useState<Stage>("Registered");
  const [title, setTitle] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!scholar) return;
    setStage(scholar.stage);
    setTitle(scholar.research_title ?? "");
  }, [scholar]);

  // The UI offers edits to admins; the API decides whether this admin covers this unit.
  const canEdit = me?.roles.includes("admin") ?? false;

  async function saveDetails(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      setData(await api<Scholar>(`/scholars/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ stage, research_title: title || null }),
      }));
      setSaved(true);
    } catch (err) {
      setSaveError(errorText(err));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!scholar) return null;
  return (
    <>
      <PageHeader eyebrow={scholar.roll_number} title={scholar.full_name}
        actions={<span className="badge">{scholar.stage}</span>} />
      <div className="profile-grid">
        <Card>
          <h2>Details</h2>
          <dl className="kv">
            <dt>Department</dt>
            <dd>{scholar.unit.name}</dd>
            <dt>Email</dt>
            <dd><a href={`mailto:${scholar.email}`}>{scholar.email}</a></dd>
            <dt>Research title</dt>
            <dd>{scholar.research_title ?? <span className="muted">Not set</span>}</dd>
            <dt>Admitted</dt>
            <dd>{scholar.admission_date ?? <span className="muted">Not recorded</span>}</dd>
            <dt>Supervisor</dt>
            <dd>{scholar.supervisor?.name ?? <span className="muted">Not assigned</span>}</dd>
            {me?.co_supervision !== "off" && (
              <>
                <dt>Co-supervisor</dt>
                <dd>{scholar.co_supervisor?.name ?? <span className="muted">None</span>}</dd>
              </>
            )}
          </dl>
        </Card>
        {canEdit && (
          <Card>
            <h2>Manage</h2>
            <form className="manage" onSubmit={saveDetails}>
              <Field label="Stage">
                <select value={stage} onChange={(e) => setStage(e.target.value as Stage)}>
                  {STAGES.map((s) => <option key={s}>{s}</option>)}
                </select>
              </Field>
              <Field label="Research title">
                <input value={title} maxLength={500} onChange={(e) => setTitle(e.target.value)} />
              </Field>
              <ErrorText>{saveError}</ErrorText>
              {saved && <p className="muted" role="status">Saved.</p>}
              <Button kind="primary" type="submit">Save details</Button>
            </form>
            <AssignCard scholar={scholar} kind="supervisor" onSaved={setData} />
            {me?.co_supervision !== "off" && (
              <AssignCard scholar={scholar} kind="co-supervisor" onSaved={setData} />
            )}
            <InviteButton userId={scholar.user_id} />
          </Card>
        )}
      </div>
      <Decisions scholarId={scholar.id} />
      {me?.modules.coursework && !me.roles.every((r) => r === "library") && (
        <div style={{ marginTop: "var(--space-5)" }}><CourseworkCard scholarId={scholar.id} /></div>
      )}
      <div className="profile-grid" style={{ marginTop: "var(--space-5)" }}>
        <Timeline scholarId={scholar.id} />
        <Comments target="scholars" recordId={scholar.id} />
      </div>
      <p className="back"><Link href="/scholars">← All scholars</Link></p>
    </>
  );
}
