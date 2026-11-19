"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Appointment, SupervisionView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const ROLE = { supervisor: "Supervisor", co_supervisor: "Co-supervisor" } as const;

function OrderForm({ row, onSaved }: { row: Appointment; onSaved: (v: SupervisionView) => void }) {
  const [open, setOpen] = useState(false);
  const [on, setOn] = useState(row.appointed_on ?? "");
  const [ref, setRef] = useState(row.order_ref ?? "");
  const [ended, setEnded] = useState(row.ended_on ?? "");
  const [error, setError] = useState<string | null>(null);
  if (!open) return <Button kind="ghost" onClick={() => setOpen(true)}>{row.appointed_on || row.order_ref || row.ended_on ? "Correct" : "Record order"}</Button>;

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await api<SupervisionView>(`/scholars/appointments/${row.id}`, {
        method: "PATCH",
        // A current appointment ends only when someone else is appointed: no end date to send.
        body: JSON.stringify({ appointed_on: on || null, order_ref: ref || null, ...(row.ended_on && { ended_on: ended }) }),
      }));
      setOpen(false);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="row" onSubmit={save}>
      <Field label="Appointed on"><input type="date" value={on} max={ended || undefined} onChange={(e) => setOn(e.target.value)} /></Field>
      <Field label="Order no."><input maxLength={100} value={ref} onChange={(e) => setRef(e.target.value)} /></Field>
      {row.ended_on && (
        <Field label="Ended on"><input type="date" required value={ended} min={on || undefined} onChange={(e) => setEnded(e.target.value)} /></Field>
      )}
      <Button kind="secondary" type="submit">Save</Button>
      <Button kind="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      <ErrorText>{error}</ErrorText>
    </form>
  );
}

/** Every supervisor and co-supervisor the scholar has had (Form IV), current first: whoever
 *  guided the scholar stays on record after a change. The admin over the unit records orders. */
export function SupervisionCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<SupervisionView>(`/scholars/${scholarId}/supervision`);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;
  return (
    <Card className="coursework">
      <h2>Supervision</h2>
      {v.appointments.length === 0 ? <p className="muted">No supervisor appointed yet.</p> : (
        <ul className="plain-list">
          {v.appointments.map((a) => (
            <li key={a.id}>
              <strong>{a.faculty.name}</strong> · {ROLE[a.role]}
              <span className="muted">
                {a.ended_on ? ` · until ${formatDate(a.ended_on)}` : " · current"}
                {a.appointed_on && ` · appointed ${formatDate(a.appointed_on)}`}
                {a.order_ref && ` · order ${a.order_ref}`}
              </span>
              {v.can_manage && <OrderForm row={a} onSaved={setData} />}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
