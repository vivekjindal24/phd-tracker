"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { Comments } from "@/components/Comments";
import { CourseworkCard } from "@/components/CourseworkCard";
import { CommitteeCard } from "@/components/CommitteeCard";
import { EthicsCard } from "@/components/EthicsCard";
import { DurationCard } from "@/components/DurationCard";
import { InviteButton } from "@/components/InviteButton";
import { MilestoneStatusBadge } from "@/components/MilestoneStatusBadge";
import { Timeline } from "@/components/Timeline";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { RequestMember } from "@/components/RequestMember";
import { CATEGORY_LABELS, GENDER_LABELS, LEFT_LABELS, MILESTONE_LABELS, STAGES, STUDY_MODE_LABELS } from "@/lib/types";
import type { Faculty, LeftReason, Milestone, Scholar, Stage } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./profile.css";

const NOT_RECORDED = <span className="muted">Not recorded</span>;

const choices = (labels: Record<string, string>) =>
  Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>);

/** A scholar fills in their own details that are still not recorded; a recorded value is the
 *  admin's to correct (the API refuses a change here). */
function OwnProfileCard({ scholar, onSaved }: { scholar: Scholar; onSaved: (s: Scholar) => void }) {
  const [v, setV] = useState({ study_mode: "", gender: "", category: "", has_disability: "" });
  const [error, setError] = useState<string | null>(null);
  const missing = {
    study_mode: scholar.study_mode === null,
    gender: scholar.gender === null,
    category: scholar.category === null,
    has_disability: scholar.has_disability === null,
  };
  if (!Object.values(missing).some(Boolean)) return null;
  const chosen = Object.entries(v).filter(([, value]) => value);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const body = Object.fromEntries(chosen.map(([k, value]) => [k, k === "has_disability" ? value === "true" : value]));
    try {
      onSaved(await api<Scholar>("/scholars/mine/profile", { method: "PUT", body: JSON.stringify(body) }));
      setV({ study_mode: "", gender: "", category: "", has_disability: "" });
    } catch (err) {
      setError(errorText(err));
    }
  }
  const field = (key: keyof typeof v, label: string, options: ReactNode) =>
    missing[key] && (
      <Field label={label}>
        <select value={v[key]} onChange={(e) => setV({ ...v, [key]: e.target.value })}>
          <option value="">Choose…</option>
          {options}
        </select>
      </Field>
    );

  return (
    <Card>
      <h2>Complete your profile</h2>
      <p className="muted">
        The university reports these to UGC and AISHE. Your gender, category and disability status are seen only by
        you, your department&apos;s admins and head, the Research Office and the Vice Chancellor — not by your
        supervisor. Once saved, ask your department&apos;s admin if something needs correcting.
      </p>
      <form className="manage" onSubmit={save}>
        {field("study_mode", "Mode", choices(STUDY_MODE_LABELS))}
        {field("gender", "Gender", choices(GENDER_LABELS))}
        {field("category", "Category", choices(CATEGORY_LABELS))}
        {field("has_disability", "Person with disability", <><option value="true">Yes</option><option value="false">No</option></>)}
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={chosen.length === 0}>Save my details</Button>
      </form>
    </Card>
  );
}

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
        hint={kind === "supervisor" ? "Only supervisors below their limit are listed." : undefined}>
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

/** Withdrawn / registration cancelled: the scholar stops counting toward caps and workloads
 *  and is reported as a drop-out (PRD Phase 4). Undo by clearing it. */
function LeftCard({ scholar, onSaved }: { scholar: Scholar; onSaved: (s: Scholar) => void }) {
  const [on, setOn] = useState(scholar.left_on ?? "");
  const [reason, setReason] = useState<LeftReason>(scholar.left_reason ?? "withdrawn");
  const [error, setError] = useState<string | null>(null);

  async function save(body: object) {
    setError(null);
    try {
      onSaved(await api<Scholar>(`/scholars/${scholar.id}`, { method: "PATCH", body: JSON.stringify(body) }));
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="assign">
      {scholar.left_on ? (
        <>
          <p><strong>{scholar.left_reason ? LEFT_LABELS[scholar.left_reason] : "Left"}</strong> on {formatDate(scholar.left_on)}</p>
          <Button kind="ghost" onClick={() => save({ left_on: null, left_reason: null })}>Undo — back in the programme</Button>
        </>
      ) : (
        <div className="row">
          <Field label="Left the programme on"><input type="date" value={on} onChange={(e) => setOn(e.target.value)} /></Field>
          <Field label="Why">
            <select value={reason} onChange={(e) => setReason(e.target.value as LeftReason)}>
              {(Object.keys(LEFT_LABELS) as LeftReason[]).map((k) => <option key={k} value={k}>{LEFT_LABELS[k]}</option>)}
            </select>
          </Field>
          <Button kind="danger" disabled={!on} onClick={() => save({ left_on: on, left_reason: reason })}>Mark as left</Button>
        </div>
      )}
      <ErrorText>{error}</ErrorText>
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
  // "" = not recorded; sent as null.
  const [profile, setProfile] = useState({ study_mode: "", gender: "", category: "", has_disability: "" });
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!scholar) return;
    setStage(scholar.stage);
    setTitle(scholar.research_title ?? "");
    setProfile({
      study_mode: scholar.study_mode ?? "",
      gender: scholar.gender ?? "",
      category: scholar.category ?? "",
      has_disability: scholar.has_disability === null ? "" : String(scholar.has_disability),
    });
  }, [scholar]);

  // The UI offers edits to admins; the API decides whether this admin covers this unit.
  const canEdit = (me?.roles.includes("admin") ?? false) && !scholar?.directory_only;
  const mayRequest =
    me?.co_supervision !== "off" &&
    !!scholar &&
    !scholar.co_supervisor &&
    !scholar.directory_only &&
    (canEdit || (!!me?.faculty_id && me.faculty_id === scholar.supervisor?.id));

  async function saveDetails(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);
    try {
      setData(await api<Scholar>(`/scholars/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          stage,
          research_title: title || null,
          study_mode: profile.study_mode || null,
          // Only someone shown the personal fields may overwrite them.
          ...(scholar?.sees_personal && {
            gender: profile.gender || null,
            category: profile.category || null,
            has_disability: profile.has_disability === "" ? null : profile.has_disability === "true",
          }),
        }),
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
        actions={<>
          <span className="badge">{scholar.stage}</span>
          {scholar.left_reason && <span className="badge badge-sent_back">{LEFT_LABELS[scholar.left_reason]}</span>}
        </>} />
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
            <dt>Mode</dt>
            <dd>{scholar.study_mode ? STUDY_MODE_LABELS[scholar.study_mode] : NOT_RECORDED}</dd>
            {scholar.sees_personal && (
              <>
                <dt>Gender</dt>
                <dd>{scholar.gender ? GENDER_LABELS[scholar.gender] : NOT_RECORDED}</dd>
                <dt>Category</dt>
                <dd>{scholar.category ? CATEGORY_LABELS[scholar.category] : NOT_RECORDED}</dd>
                <dt>Person with disability</dt>
                <dd>{scholar.has_disability === null ? NOT_RECORDED : scholar.has_disability ? "Yes" : "No"}</dd>
              </>
            )}
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
        {me?.scholar_id === scholar.id && <OwnProfileCard scholar={scholar} onSaved={setData} />}
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
              <Field label="Mode">
                <select value={profile.study_mode} onChange={(e) => setProfile({ ...profile, study_mode: e.target.value })}>
                  <option value="">Not recorded</option>
                  {Object.entries(STUDY_MODE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
              </Field>
              {scholar.sees_personal && (
                <>
                  <Field label="Gender">
                    <select value={profile.gender} onChange={(e) => setProfile({ ...profile, gender: e.target.value })}>
                      <option value="">Not recorded</option>
                      {Object.entries(GENDER_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </Field>
                  <Field label="Category">
                    <select value={profile.category} onChange={(e) => setProfile({ ...profile, category: e.target.value })}>
                      <option value="">Not recorded</option>
                      {Object.entries(CATEGORY_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                    </select>
                  </Field>
                  <Field label="Person with disability" hint="Seen only by the scholar, their department's admins and head, the Research Office and the Vice Chancellor — as are gender and category.">
                    <select value={profile.has_disability} onChange={(e) => setProfile({ ...profile, has_disability: e.target.value })}>
                      <option value="">Not recorded</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </Field>
                </>
              )}
              <ErrorText>{saveError}</ErrorText>
              {saved && <p className="muted" role="status">Saved.</p>}
              <Button kind="primary" type="submit">Save details</Button>
            </form>
            <AssignCard scholar={scholar} kind="supervisor" onSaved={setData} />
            {me?.co_supervision !== "off" && (
              <AssignCard scholar={scholar} kind="co-supervisor" onSaved={setData} />
            )}
            {mayRequest && (
              <RequestMember kind="co_supervisor" targetId={scholar.id} title="Ask someone from another department" />
            )}
            <LeftCard scholar={scholar} onSaved={setData} />
            <InviteButton userId={scholar.user_id} />
          </Card>
        )}
      </div>
      {!canEdit && mayRequest && (
        <Card>
          <RequestMember kind="co_supervisor" targetId={scholar.id} title="Ask someone to co-supervise" />
        </Card>
      )}
      {scholar.directory_only ? null : <Records scholar={scholar} />}
      <p className="back"><Link href="/scholars">← All scholars</Link></p>
    </>
  );
}

function Records({ scholar }: { scholar: Scholar }) {
  const { me } = useSession();
  return (
    <>
      <Decisions scholarId={scholar.id} />
      {me?.roles.some((r) => r !== "exam_office" && r !== "library") && (
        <>
          <div style={{ marginTop: "var(--space-5)" }}><CommitteeCard scholarId={scholar.id} /></div>
          <div style={{ marginTop: "var(--space-5)" }}><EthicsCard scholarId={scholar.id} /></div>
          <div style={{ marginTop: "var(--space-5)" }}><DurationCard scholarId={scholar.id} /></div>
        </>
      )}
      {me?.modules.coursework && !me.roles.every((r) => r === "library") && (
        <div style={{ marginTop: "var(--space-5)" }}><CourseworkCard scholarId={scholar.id} /></div>
      )}
      <div className="profile-grid" style={{ marginTop: "var(--space-5)" }}>
        <Timeline scholarId={scholar.id} />
        <Comments target="scholars" recordId={scholar.id} />
      </div>
    </>
  );
}
