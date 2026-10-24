"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Attachments } from "@/components/Attachments";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { CONFERENCE_TYPE_LABELS } from "@/lib/types";
import type { Conference, ConferenceType } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function AddConference({ onAdded }: { onAdded: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState<ConferenceType>("paper_presented");
  const [when, setWhen] = useState("");
  const [place, setPlace] = useState("");
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/conferences", {
        method: "POST",
        body: JSON.stringify({ event_name: name, event_type: type, event_date: when, place, title: title || null }),
      });
      setName(""); setWhen(""); setPlace(""); setTitle("");
      onAdded();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>Add a conference or talk</h2>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          <Field label="Event">
            <input required maxLength={500} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Field label="What you did">
            <select value={type} onChange={(e) => setType(e.target.value as ConferenceType)}>
              {(Object.keys(CONFERENCE_TYPE_LABELS) as ConferenceType[]).map((k) => (
                <option key={k} value={k}>{CONFERENCE_TYPE_LABELS[k]}</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="row">
          <Field label="Date">
            <input type="date" required value={when} onChange={(e) => setWhen(e.target.value)} />
          </Field>
          <Field label="Place">
            <input maxLength={200} value={place} onChange={(e) => setPlace(e.target.value)} />
          </Field>
        </div>
        <Field label="Title of your paper or talk" hint="Leave empty if you attended.">
          <input maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Add"}</Button>
      </form>
    </Card>
  );
}

export default function ConferencesPage() {
  const { me } = useSession();
  const { data, error, reload } = useFetch<Conference[]>("/conferences?limit=500");
  const [open, setOpen] = useState<string | null>(null);
  const [actError, setActError] = useState<string | null>(null);
  const isScholar = me?.scholar_id != null;

  async function remove(c: Conference) {
    setActError(null);
    try {
      await api(`/conferences/${c.id}`, { method: "DELETE" });
      await reload();
    } catch (e) {
      setActError(errorText(e));
    }
  }

  const selected = data?.find((c) => c.id === open);
  return (
    <>
      <PageHeader eyebrow="Research record" title="Conferences & talks" />
      {isScholar && <AddConference onAdded={reload} />}
      <ErrorText>{error ?? actError}</ErrorText>
      {data && (
        <Table label="Conferences and talks" head={["Date", "Event", "Scholar", "Contribution", ""]}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>Nothing recorded yet</h2>
              <p>Papers presented, posters, invited talks and workshops appear here.</p>
            </div>
          }>
          {data.map((c) => (
            <tr key={c.id}>
              <td className="mono">{formatDate(c.event_date)}</td>
              <td>{c.event_name}{c.place && <div className="muted">{c.place}</div>}</td>
              <td>{c.scholar.name}</td>
              <td>{CONFERENCE_TYPE_LABELS[c.event_type]}{c.title && <div className="muted">{c.title}</div>}</td>
              <td>
                <div className="row">
                  <Button kind="ghost" onClick={() => setOpen(open === c.id ? null : c.id)}>
                    {open === c.id ? "Hide certificate" : "Certificate"}
                  </Button>
                  {c.can_edit && <Button kind="ghost" onClick={() => remove(c)}>Remove</Button>}
                </div>
              </td>
            </tr>
          ))}
        </Table>
      )}
      {selected && (
        <div style={{ marginTop: "var(--space-5)" }}>
          <Attachments table="conferences" recordId={selected.id} canUpload={selected.can_edit}
            title={`Certificate · ${selected.event_name}`} />
        </div>
      )}
    </>
  );
}
