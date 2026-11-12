"use client";

import { type FormEvent, useState } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Ref } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

type Period = { starts_on: string; ends_on: string };
type StandIns = {
  mine: (Period & { stand_in: Ref }) | null;
  standing_in_for: (Period & { supervisor: Ref })[];
};

const today = () => new Date().toISOString().slice(0, 10);
const span = (p: Period) => `${formatDate(p.starts_on)} – ${formatDate(p.ends_on)}`;

/** Faculty only (PRD F3): name a colleague who approves at the supervisor step while you are
 *  away, and see whom you are standing in for. The API owns every rule. */
export function StandInCard() {
  const { data, error, setData } = useFetch<StandIns>("/faculty/me/stand-in");
  // 403 for faculty who do not supervise: they have nobody to name, and the form stays hidden.
  const { data: colleagues } = useFetch<Ref[]>("/faculty/me/stand-in/candidates");
  const [who, setWho] = useState("");
  const [from, setFrom] = useState(today());
  const [to, setTo] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setSaveError(null);
    try {
      setData(await api<StandIns>("/faculty/me/stand-in", {
        method: "PUT",
        body: JSON.stringify({ stand_in_id: who, starts_on: from, ends_on: to }),
      }));
      setWho("");
      setTo("");
    } catch (err) {
      setSaveError(errorText(err));
    }
  }
  async function remove() {
    setSaveError(null);
    try {
      setData(await api<StandIns>("/faculty/me/stand-in", { method: "DELETE" }));
    } catch (err) {
      setSaveError(errorText(err));
    }
  }

  if (error) return <Card><h2>Stand-in</h2><ErrorText>{error}</ErrorText></Card>;
  if (!data) return null;
  return (
    <Card>
      <h2>Stand-in while you are away</h2>
      <p className="muted">
        A stand-in can approve or send back what waits at your supervisor step, and for those dates sees your
        scholars&apos; records as you do. Each action is recorded as done on your behalf.
      </p>
      {data.mine ? (
        <p>
          <strong>{data.mine.stand_in.name}</strong> stands in for you, {span(data.mine)}.{" "}
          <Button kind="ghost" onClick={remove}>End it</Button>
        </p>
      ) : colleagues && colleagues.length === 0 ? (
        <p className="muted">No other supervisor in your department to name.</p>
      ) : null}
      {colleagues && colleagues.length > 0 && (
        <form className="stack-form" onSubmit={save}>
          <Field label={data.mine ? "Replace with" : "Colleague"} hint="Supervisors of your own department.">
            <select required value={who} onChange={(e) => setWho(e.target.value)}>
              <option value="">Choose…</option>
              {colleagues.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <div className="row">
            <Field label="From">
              <input type="date" required value={from} onChange={(e) => setFrom(e.target.value)} />
            </Field>
            <Field label="Until">
              <input type="date" required min={from} value={to} onChange={(e) => setTo(e.target.value)} />
            </Field>
          </div>
          <ErrorText>{saveError}</ErrorText>
          <Button kind="primary" type="submit">Name stand-in</Button>
        </form>
      )}
      {!colleagues && <ErrorText>{saveError}</ErrorText>}
      {data.standing_in_for.length > 0 && (
        <>
          <h3>You are standing in for</h3>
          <ul>
            {data.standing_in_for.map((s) => (
              <li key={s.supervisor.id}><strong>{s.supervisor.name}</strong>, {span(s)}</li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
