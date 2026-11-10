"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { CommitteeView, Faculty } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

type Save = (path: string, method: "POST" | "DELETE", body?: unknown) => Promise<void>;

function AddMember({ scholarId, save }: { scholarId: string; save: Save }) {
  const [outside, setOutside] = useState(false);
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const { data: found } = useFetch<Faculty[]>(!outside && q.length >= 2 ? `/faculty?q=${encodeURIComponent(q)}&limit=10` : null);
  const path = `/scholars/${scholarId}/committee`;

  async function addOutside(e: FormEvent) {
    e.preventDefault();
    await save(path, "POST", { name, institution });
    setName("");
    setInstitution("");
  }

  return (
    <div className="verify">
      <h3>Add a member</h3>
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
                  <Button kind="ghost" onClick={() => save(path, "POST", { faculty_id: f.id }).then(() => setQ(""))}>
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

/** The scholar's Research Advisory Committee: the supervisor convenes, the rest are recorded here. */
export function CommitteeCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<CommitteeView>(`/scholars/${scholarId}/committee`);
  const [actError, setActError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;

  const save: Save = async (path, method, body) => {
    setActError(null);
    try {
      setData(await api<CommitteeView>(path, { method, body: body ? JSON.stringify(body) : undefined }));
    } catch (e) {
      setActError(errorText(e));
    }
  };

  return (
    <Card className="coursework">
      <h2>Research Advisory Committee</h2>
      <ul className="plain-list">
        <li><strong>{v.convener ?? "No supervisor assigned"}</strong> · <span className="muted">Supervisor, convener</span></li>
        {v.members.map((m) => (
          <li key={m.id}>
            <strong>{m.name}</strong> · {m.institution}{m.external && <span className="muted"> · outside expert</span>}
            {v.can_manage && <Button kind="ghost" onClick={() => save(`/committee-members/${m.id}`, "DELETE")}>Remove</Button>}
          </li>
        ))}
      </ul>
      {v.members.length === 0 && <p className="muted">No other members recorded yet.</p>}
      {v.can_manage && <AddMember scholarId={scholarId} save={save} />}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
