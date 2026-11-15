"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import type { ClaimContent, ItemView } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

/** The month claimed; the scholar corrects leave days and the note while it is theirs to edit. */
export function ClaimDetails({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as ClaimContent;
  const [leaveDays, setLeaveDays] = useState(String(c.leave_days));
  const [note, setNote] = useState(c.note);
  const [error, setError] = useState<string | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await api<ItemView>(`/fellowship-claims/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ leave_days: Number(leaveDays), note }),
      }));
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Fellowship claim</h2>
      <dl className="kv">
        <dt>Month</dt><dd>{formatMonth(c.month)}</dd>
        <dt>Amount</dt><dd className="mono">{formatMoney(c.amount)} <span className="muted">fellowship + HRA</span></dd>
        {!item.can_edit && <><dt>Leave taken</dt><dd>{c.leave_days} {c.leave_days === 1 ? "day" : "days"}</dd></>}
        {!item.can_edit && c.note && <><dt>Note</dt><dd className="prose">{c.note}</dd></>}
      </dl>
      {item.can_edit && (
        <form className="stack-form" onSubmit={save}>
          <Field label="Days of leave taken this month">
            <input type="number" required min={0} max={31} step={1} value={leaveDays} onChange={(e) => setLeaveDays(e.target.value)} />
          </Field>
          <Field label="Note" hint="Optional: anything your supervisor should know about this month.">
            <textarea value={note} maxLength={4000} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <ErrorText>{error}</ErrorText>
          <Button kind="secondary" type="submit" disabled={Number(leaveDays) === c.leave_days && note === c.note}>Save changes</Button>
        </form>
      )}
    </Card>
  );
}
