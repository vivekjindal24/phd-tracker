"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { ScholarSearch } from "@/components/ScholarSearch";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { ADVISORY_ROLES, COMMITTEE_ROLE_LABELS, COMMITTEE_SEAT_LABELS, DEPARTMENT_ROLES } from "@/lib/types";
import type { CommitteeFormation, CommitteeMember, CommitteeRole, CommitteeSeat, CommitteeView, Faculty } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

/** Resolves true when saved; a failure shows on the card and leaves the form open. */
type Save = (path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) => Promise<boolean>;

const SEATS = Object.keys(COMMITTEE_SEAT_LABELS) as CommitteeSeat[];
const FACULTY_SEATS = SEATS.filter((s) => s !== "scholar");

function RoleSelect({ roles, value, onChange }: { roles: CommitteeRole[]; value: CommitteeRole; onChange: (r: CommitteeRole) => void }) {
  return (
    <select aria-label="Role" value={value} onChange={(e) => onChange(e.target.value as CommitteeRole)}>
      {roles.map((r) => <option key={r} value={r}>{COMMITTEE_ROLE_LABELS[r]}</option>)}
    </select>
  );
}

function SeatSelect({ value, onChange }: { value: CommitteeSeat; onChange: (s: CommitteeSeat) => void }) {
  return (
    <select aria-label="Seat" value={value} onChange={(e) => onChange(e.target.value as CommitteeSeat)}>
      {FACULTY_SEATS.map((s) => <option key={s} value={s}>{COMMITTEE_SEAT_LABELS[s]}</option>)}
    </select>
  );
}

/** When the committee was formed and the order that formed it: a new version, or a correction. */
function FormationForm({ title, initial, onSubmit, onCancel }: {
  title: string;
  initial?: CommitteeFormation;
  onSubmit: (body: { formed_on: string; reference: string | null; notes: string }) => Promise<unknown>;
  onCancel?: () => void;
}) {
  const [formedOn, setFormedOn] = useState(initial?.formed_on ?? "");
  const [reference, setReference] = useState(initial?.reference ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");

  async function submit(e: FormEvent) {
    e.preventDefault();
    await onSubmit({ formed_on: formedOn, reference: reference || null, notes });
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>{title}</h3>
      <div className="row">
        <Field label="Formed on"><input type="date" required value={formedOn} onChange={(e) => setFormedOn(e.target.value)} /></Field>
        <Field label="Order or resolution no."><input maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} /></Field>
      </div>
      <Field label="Notes"><input maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <Button kind="secondary" type="submit">Save</Button>
      {onCancel && <Button kind="ghost" onClick={onCancel}>Cancel</Button>}
    </form>
  );
}

type Who = "faculty" | "outside" | "scholar";

function AddMember({ formationId, department, save }: { formationId: string; department: boolean; save: Save }) {
  const [who, setWho] = useState<Who>("faculty");
  const [role, setRole] = useState<CommitteeRole>("member");
  const [seat, setSeat] = useState<CommitteeSeat>("faculty_nominee");
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const { data: found } = useFetch<Faculty[]>(who === "faculty" && q.length >= 2 ? `/faculty?q=${encodeURIComponent(q)}&limit=10` : null);
  const path = `/committee-formations/${formationId}/members`;
  // A department's members sit in a seat; a scholar always in the scholar's seat.
  const placed = (person: object) => ({
    ...person,
    role,
    ...(department ? { seat: who === "scholar" ? "scholar" : seat } : {}),
  });

  async function addOutside(e: FormEvent) {
    e.preventDefault();
    if (!(await save(path, "POST", placed({ name, institution })))) return;
    setName("");
    setInstitution("");
  }

  return (
    <div className="verify">
      <h3>Add a member</h3>
      <div className="row">
        <Field label="Who">
          <select value={who} onChange={(e) => setWho(e.target.value as Who)}>
            <option value="faculty">Faculty of this university</option>
            <option value="outside">An expert from outside this university</option>
            {department && <option value="scholar">A PhD scholar of this department</option>}
          </select>
        </Field>
        <Field label="Role"><RoleSelect roles={department ? DEPARTMENT_ROLES : ADVISORY_ROLES} value={role} onChange={setRole} /></Field>
        {department && who !== "scholar" && <Field label="Seat"><SeatSelect value={seat} onChange={setSeat} /></Field>}
      </div>
      {who === "outside" && (
        <form onSubmit={addOutside}>
          <div className="row">
            <Field label="Name"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Institution"><input required maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
          </div>
          <Button kind="secondary" type="submit">Add</Button>
        </form>
      )}
      {who === "scholar" && <ScholarSearch onPick={(s) => save(path, "POST", placed({ scholar_member_id: s.id }))} />}
      {who === "faculty" && (
        <>
          <Field label="Find a faculty member" hint="Name. You see the faculty your role lets you see.">
            <input value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          {found && (
            <ul className="plain-list">
              {found.length === 0 && <li className="muted">Nobody found.</li>}
              {found.map((f) => (
                <li key={f.id}>
                  <Button kind="ghost" onClick={() => save(path, "POST", placed({ faculty_id: f.id })).then((ok) => ok && setQ(""))}>
                    {f.full_name} · {f.unit.name}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

/** Correct an outside expert's name or institution, on any version. */
function FixName({ member, save }: { member: CommitteeMember; save: Save }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(member.name);
  const [institution, setInstitution] = useState(member.institution);
  if (!open) return <Button kind="ghost" onClick={() => setOpen(true)}>Fix name</Button>;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await save(`/committee-members/${member.id}`, "PATCH", { name, institution })) setOpen(false);
  }

  return (
    <form className="row" onSubmit={submit}>
      <Field label="Name"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Institution"><input required maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
      <Button kind="secondary" type="submit">Save</Button>
      <Button kind="ghost" onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}

/** One version's members. `save` lets the record's keepers correct wording on any version;
 *  `current` also lets them change roles, seats and membership. */
function Members({ formation, department, save, current }: {
  formation: CommitteeFormation;
  department: boolean;
  save?: Save;
  current?: boolean;
}) {
  const patch = (m: CommitteeMember, body: object) => save?.(`/committee-members/${m.id}`, "PATCH", body);
  return (
    <ul className="plain-list">
      {!department && (
        <li>
          <strong>{formation.secretary ?? "No supervisor assigned"}</strong> · <span className="muted">Supervisor, Secretary &amp; Member</span>
        </li>
      )}
      {formation.members.map((m) => (
        <li key={m.id}>
          <strong>{m.name}</strong> · {m.institution}{m.external && <span className="muted"> · outside expert</span>}
          {" · "}
          {save && current ? (
            <>
              <RoleSelect roles={department ? DEPARTMENT_ROLES : ADVISORY_ROLES} value={m.role} onChange={(role) => patch(m, { role })} />
              {m.seat && m.seat !== "scholar" && <SeatSelect value={m.seat} onChange={(seat) => patch(m, { seat })} />}
              <Button kind="ghost" onClick={() => save(`/committee-members/${m.id}`, "DELETE")}>Remove</Button>
            </>
          ) : (
            <span className="muted">{COMMITTEE_ROLE_LABELS[m.role]}</span>
          )}
          {m.seat && !(save && current && m.seat !== "scholar") && <span className="muted"> · {COMMITTEE_SEAT_LABELS[m.seat]}</span>}
          {save && m.external && <FixName member={m} save={save} />}
        </li>
      ))}
      {formation.members.length === 0 && <li className="muted">{department ? "No members recorded yet." : "No other members recorded yet."}</li>}
    </ul>
  );
}

const formedLine = (f: CommitteeFormation) =>
  `Formed ${formatDate(f.formed_on)}${f.reference ? ` · ${f.reference}` : ""}${f.notes ? ` · ${f.notes}` : ""}`;

/** An earlier version: frozen membership, but its wording may be corrected. */
function EarlierVersion({ formation, department, save }: { formation: CommitteeFormation; department: boolean; save?: Save }) {
  const [correcting, setCorrecting] = useState(false);
  return (
    <div>
      <p className="muted">{formedLine(formation)}</p>
      <Members formation={formation} department={department} save={save} />
      {save && !correcting && <Button kind="ghost" onClick={() => setCorrecting(true)}>Correct date or order</Button>}
      {save && correcting && (
        <FormationForm
          title="Correct this version"
          initial={formation}
          onSubmit={(body) => save(`/committee-formations/${formation.id}`, "PATCH", body).then((ok) => ok && setCorrecting(false))}
          onCancel={() => setCorrecting(false)}
        />
      )}
    </div>
  );
}

/** A committee in versions (PRD F9b): a scholar's Research Advisory Committee
 *  (`/scholars/{id}/committee`) or a department's research committee (`/org-units/{id}/committee`).
 *  Shows the current version, and earlier ones as history. */
export function CommitteeCard({ path, department = false }: { path: string; department?: boolean }) {
  const { data: v, error, setData } = useFetch<CommitteeView>(path);
  const [actError, setActError] = useState<string | null>(null);
  const [editing, setEditing] = useState<"none" | "correct" | "reform">("none");
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;

  const save: Save = async (to, method, body) => {
    setActError(null);
    try {
      setData(await api<CommitteeView>(to, { method, body: body ? JSON.stringify(body) : undefined }));
      setEditing("none");
      return true;
    } catch (e) {
      setActError(errorText(e));
      return false;
    }
  };
  const [current, ...earlier] = v.formations;
  const formPath = `${path}/formations`;
  const reform = department ? "Re-constitute the committee" : "Re-form the committee";
  const keep = v.can_manage ? save : undefined;

  return (
    <Card className="coursework">
      <h2>{v.title}</h2>
      {!current ? (
        <>
          <p className="muted">No committee formed yet.</p>
          {v.can_manage && <FormationForm title="Record its formation" onSubmit={(body) => save(formPath, "POST", body)} />}
        </>
      ) : (
        <>
          <p className="muted">{formedLine(current)}</p>
          <Members formation={current} department={department} save={keep} current />
          {v.can_manage && editing === "none" && (
            <div className="row">
              <Button kind="ghost" onClick={() => setEditing("correct")}>Correct date or order</Button>
              <Button kind="ghost" onClick={() => setEditing("reform")}>{reform}</Button>
              <Button kind="ghost" onClick={() => save(`/committee-formations/${current.id}`, "DELETE")}>
                {earlier.length ? "Withdraw this version" : "Withdraw"}
              </Button>
            </div>
          )}
          {editing === "correct" && (
            <FormationForm
              title="Correct this version"
              initial={current}
              onSubmit={(body) => save(`/committee-formations/${current.id}`, "PATCH", body)}
              onCancel={() => setEditing("none")}
            />
          )}
          {editing === "reform" && (
            <>
              <FormationForm title={reform} onSubmit={(body) => save(formPath, "POST", body)} onCancel={() => setEditing("none")} />
              <p className="muted">The new version starts with the current members; change them after saving.</p>
            </>
          )}
          {v.can_manage && editing === "none" && <AddMember formationId={current.id} department={department} save={save} />}
          {earlier.length > 0 && (
            <details>
              <summary>Earlier versions ({earlier.length})</summary>
              {earlier.map((f) => <EarlierVersion key={f.id} formation={f} department={department} save={keep} />)}
            </details>
          )}
        </>
      )}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
