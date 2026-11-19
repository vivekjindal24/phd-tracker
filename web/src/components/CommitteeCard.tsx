"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { COMMITTEE_ROLE_LABELS } from "@/lib/types";
import type { CommitteeFormation, CommitteeRole, CommitteeView, Faculty } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

type Save = (path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown) => Promise<void>;

const ROLES = Object.keys(COMMITTEE_ROLE_LABELS) as CommitteeRole[];

function RoleSelect({ value, onChange }: { value: CommitteeRole; onChange: (r: CommitteeRole) => void }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value as CommitteeRole)}>
      {ROLES.map((r) => <option key={r} value={r}>{COMMITTEE_ROLE_LABELS[r]}</option>)}
    </select>
  );
}

/** When the committee was formed and the order that formed it: a new version, or a correction. */
function FormationForm({ title, initial, onSubmit, onCancel }: {
  title: string;
  initial?: CommitteeFormation;
  onSubmit: (body: { formed_on: string; reference: string | null; notes: string }) => Promise<void>;
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

function AddMember({ formationId, save }: { formationId: string; save: Save }) {
  const [outside, setOutside] = useState(false);
  const [role, setRole] = useState<CommitteeRole>("member");
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const { data: found } = useFetch<Faculty[]>(!outside && q.length >= 2 ? `/faculty?q=${encodeURIComponent(q)}&limit=10` : null);
  const path = `/committee-formations/${formationId}/members`;

  async function addOutside(e: FormEvent) {
    e.preventDefault();
    await save(path, "POST", { name, institution, role });
    setName("");
    setInstitution("");
  }

  return (
    <div className="verify">
      <h3>Add a member</h3>
      <Field label="Role"><RoleSelect value={role} onChange={setRole} /></Field>
      <label className="check">
        <input type="checkbox" checked={outside} onChange={(e) => setOutside(e.target.checked)} />
        An expert from outside this university
      </label>
      {outside ? (
        <form onSubmit={addOutside}>
          <div className="row">
            <Field label="Name"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Institution"><input required maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
          </div>
          <Button kind="secondary" type="submit">Add</Button>
        </form>
      ) : (
        <>
          <Field label="Find a faculty member" hint="Name. You see the faculty your role lets you see.">
            <input value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          {found && (
            <ul className="plain-list">
              {found.length === 0 && <li className="muted">Nobody found.</li>}
              {found.map((f) => (
                <li key={f.id}>
                  <Button kind="ghost" onClick={() => save(path, "POST", { faculty_id: f.id, role }).then(() => setQ(""))}>
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

/** One version's members; the current version's are editable by those who keep the record. */
function Members({ formation, save }: { formation: CommitteeFormation; save?: Save }) {
  return (
    <ul className="plain-list">
      <li>
        <strong>{formation.secretary ?? "No supervisor assigned"}</strong> · <span className="muted">Supervisor, Secretary &amp; Member</span>
      </li>
      {formation.members.map((m) => (
        <li key={m.id}>
          <strong>{m.name}</strong> · {m.institution}{m.external && <span className="muted"> · outside expert</span>}
          {" · "}
          {save ? (
            <>
              <RoleSelect value={m.role} onChange={(role) => save(`/committee-members/${m.id}`, "PATCH", { role })} />
              <Button kind="ghost" onClick={() => save(`/committee-members/${m.id}`, "DELETE")}>Remove</Button>
            </>
          ) : (
            <span className="muted">{COMMITTEE_ROLE_LABELS[m.role]}</span>
          )}
        </li>
      ))}
      {formation.members.length === 0 && <li className="muted">No other members recorded yet.</li>}
    </ul>
  );
}

const formedLine = (f: CommitteeFormation) =>
  `Formed ${formatDate(f.formed_on)}${f.reference ? ` · ${f.reference}` : ""}${f.notes ? ` · ${f.notes}` : ""}`;

/** The scholar's Research Advisory Committee: the current version, and earlier ones as history (PRD F9b). */
export function CommitteeCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<CommitteeView>(`/scholars/${scholarId}/committee`);
  const [actError, setActError] = useState<string | null>(null);
  const [editing, setEditing] = useState<"none" | "correct" | "reform">("none");
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;

  const save: Save = async (path, method, body) => {
    setActError(null);
    try {
      setData(await api<CommitteeView>(path, { method, body: body ? JSON.stringify(body) : undefined }));
      setEditing("none");
    } catch (e) {
      setActError(errorText(e));
    }
  };
  const [current, ...earlier] = v.formations;
  const formPath = `/scholars/${scholarId}/committee/formations`;

  return (
    <Card className="coursework">
      <h2>Research Advisory Committee</h2>
      {!current ? (
        <>
          <p className="muted">No committee formed yet.</p>
          {v.can_manage && <FormationForm title="Record its formation" onSubmit={(body) => save(formPath, "POST", body)} />}
        </>
      ) : (
        <>
          <p className="muted">{formedLine(current)}</p>
          <Members formation={current} save={v.can_manage ? save : undefined} />
          {v.can_manage && editing === "none" && (
            <div className="row">
              <Button kind="ghost" onClick={() => setEditing("correct")}>Correct date or order</Button>
              <Button kind="ghost" onClick={() => setEditing("reform")}>Re-form the committee</Button>
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
            <FormationForm
              title="Re-form the committee"
              onSubmit={(body) => save(formPath, "POST", body)}
              onCancel={() => setEditing("none")}
            />
          )}
          {editing === "reform" && <p className="muted">The new version starts with the current members; change them after saving.</p>}
          {v.can_manage && editing === "none" && <AddMember formationId={current.id} save={save} />}
          {earlier.length > 0 && (
            <details>
              <summary>Earlier versions ({earlier.length})</summary>
              {earlier.map((f) => (
                <div key={f.id}>
                  <p className="muted">{formedLine(f)}</p>
                  <Members formation={f} />
                </div>
              ))}
            </details>
          )}
        </>
      )}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
