"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { VIVA_BOARD_ROLE_LABELS } from "@/lib/types";
import type { Faculty, ItemView, VivaArrangementContent, VivaBoard, VivaBoardRole } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const ROLES = Object.keys(VIVA_BOARD_ROLE_LABELS) as VivaBoardRole[];

/** A datetime-local value in the viewer's own zone, and back to an instant for the API. */
const toLocalInput = (iso: string) => {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};
export const fromLocalInput = (value: string) => new Date(value).toISOString();

/** When and where, editable by the Exam Office while it is a draft or sent back. */
export function ArrangementFields({ initial, submitLabel, onSubmit }: {
  initial?: VivaArrangementContent;
  submitLabel: string;
  onSubmit: (body: { scheduled_at: string; venue: string; online_link: string | null; notes: string }) => Promise<void>;
}) {
  const [at, setAt] = useState(initial ? toLocalInput(initial.scheduled_at) : "");
  const [venue, setVenue] = useState(initial?.venue ?? "");
  const [link, setLink] = useState(initial?.online_link ?? "");
  const [notes, setNotes] = useState(initial?.notes ?? "");

  async function submit(e: FormEvent) {
    e.preventDefault();
    await onSubmit({ scheduled_at: fromLocalInput(at), venue, online_link: link || null, notes });
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <div className="row">
        <Field label="Date and time"><input type="datetime-local" required value={at} onChange={(e) => setAt(e.target.value)} /></Field>
        <Field label="Venue"><input maxLength={500} value={venue} onChange={(e) => setVenue(e.target.value)} /></Field>
        <Field label="Online link" hint="If held online or hybrid."><input type="url" maxLength={500} value={link} onChange={(e) => setLink(e.target.value)} /></Field>
      </div>
      <Field label="Notes"><input maxLength={4000} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
      <Button kind="secondary" type="submit">{submitLabel}</Button>
    </form>
  );
}

function AddBoardMember({ arrangementId, onSaved }: { arrangementId: string; onSaved: (b: VivaBoard) => void }) {
  const [role, setRole] = useState<VivaBoardRole>("external_examiner");
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [institution, setInstitution] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const { data: found } = useFetch<Faculty[]>(role !== "external_examiner" && q.length >= 2 ? `/faculty?q=${encodeURIComponent(q)}&limit=10` : null);

  async function add(body: object) {
    setError(null);
    try {
      onSaved(await api<VivaBoard>(`/viva-arrangements/${arrangementId}/board`, { method: "POST", body: JSON.stringify({ role, ...body }) }));
      setQ(""); setName(""); setInstitution(""); setEmail("");
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="verify">
      <h3>Add to the board</h3>
      <Field label="Role">
        <select value={role} onChange={(e) => setRole(e.target.value as VivaBoardRole)}>
          {ROLES.map((r) => <option key={r} value={r}>{VIVA_BOARD_ROLE_LABELS[r]}</option>)}
        </select>
      </Field>
      {role !== "external_examiner" && (
        <>
          <Field label="Find a faculty member" hint="Or fill in an outside person below.">
            <input value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
          {found && (
            <ul className="plain-list">
              {found.length === 0 && <li className="muted">Nobody found.</li>}
              {found.map((f) => (
                <li key={f.id}><Button kind="ghost" onClick={() => add({ faculty_id: f.id })}>{f.full_name} · {f.unit.name}</Button></li>
              ))}
            </ul>
          )}
        </>
      )}
      <form onSubmit={(e) => { e.preventDefault(); add({ name, institution, email }); }}>
          <div className="row">
            <Field label="Name"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Institution"><input required maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
            <Field label="Email" hint="The invitation goes here."><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
          </div>
          <Button kind="secondary" type="submit">Add</Button>
      </form>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** Form XI: the supervisor always sits; the rest by role. External examiners stay unnamed to
 *  the scholar and guide until the viva is recorded. */
function Board({ item }: { item: ItemView }) {
  const { data: board, error, setData } = useFetch<VivaBoard>(`/viva-arrangements/${item.id}/board`);
  const [actError, setActError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!board) return null;

  async function remove(id: string) {
    setActError(null);
    try {
      setData(await api<VivaBoard>(`/viva-board-members/${id}`, { method: "DELETE" }));
    } catch (e) {
      setActError(errorText(e));
    }
  }
  async function invite() {
    setActError(null);
    try {
      const res = await api<{ sent: number }>(`/viva-arrangements/${item.id}/invite`, { method: "POST" });
      setSent(`Invitation sent to ${res.sent} external examiner${res.sent === 1 ? "" : "s"}.`);
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <Card>
      <h2>Viva board</h2>
      <ul className="plain-list">
        <li><strong>{board.supervisor ?? "No supervisor assigned"}</strong> · <span className="muted">Supervisor</span></li>
        {board.members.map((m) => (
          <li key={m.id}>
            <strong>{m.name ?? "Name withheld until the viva"}</strong>
            {m.institution && ` · ${m.institution}`}
            <span className="muted"> · {VIVA_BOARD_ROLE_LABELS[m.role]}</span>
            {m.email && <span className="muted"> · {m.email}</span>}
            {board.can_edit && <Button kind="ghost" onClick={() => remove(m.id)}>Remove</Button>}
          </li>
        ))}
      </ul>
      {board.can_edit && <AddBoardMember arrangementId={item.id} onSaved={setData} />}
      {board.can_invite && (
        board.email_configured
          ? <Button kind="primary" onClick={invite}>Email the external examiners</Button>
          : <p className="muted">Email is not configured on this server; send the invitation yourself.</p>
      )}
      {sent && <p role="status">{sent}</p>}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}

/** Approval to hold the viva (Form X): when and where, then its board. */
export function VivaArrangementDetails({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as VivaArrangementContent;
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  async function withdraw() {
    setError(null);
    try {
      await api(`/viva-arrangements/${item.id}`, { method: "DELETE" });
      router.push(`/items/thesis_submission/${c.thesis_id}`);
    } catch (e) {
      setError(errorText(e));
    }
  }

  async function save(body: object) {
    setError(null);
    try {
      onSaved(await api<ItemView>(`/viva-arrangements/${item.id}`, { method: "PATCH", body: JSON.stringify(body) }));
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <>
      <Card>
        <h2>Viva</h2>
        {item.can_edit ? (
          <>
            <ArrangementFields initial={c} submitLabel="Save changes" onSubmit={save} />
            <Button kind="ghost" onClick={withdraw}>Withdraw this arrangement</Button>
          </>
        ) : (
          <dl className="kv">
            <dt>Date and time</dt><dd>{new Date(c.scheduled_at).toLocaleString()}</dd>
            {c.venue && <><dt>Venue</dt><dd>{c.venue}</dd></>}
            {c.online_link && <><dt>Online</dt><dd><a href={c.online_link} rel="noopener noreferrer" target="_blank">{c.online_link}</a></dd></>}
            {c.notes && <><dt>Notes</dt><dd className="prose">{c.notes}</dd></>}
            {c.invited_at && <><dt>Examiners emailed</dt><dd>{formatDate(c.invited_at.slice(0, 10))}</dd></>}
          </dl>
        )}
        <ErrorText>{error}</ErrorText>
      </Card>
      <Board item={item} />
    </>
  );
}
