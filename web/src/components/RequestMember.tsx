"use client";

import { type FormEvent, useState } from "react";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { errorText } from "@/lib/useFetch";

/** Ask someone outside this department by email. The directory stays closed, so the reply
 *  never says whether the address belongs to a faculty member. */
export function RequestMember({
  kind,
  targetId,
  title,
}: {
  kind: "seminar_panel" | "co_supervisor";
  targetId: string;
  title: string;
}) {
  const [email, setEmail] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSent(false);
    try {
      const target = kind === "seminar_panel" ? { seminar_id: targetId } : { scholar_id: targetId };
      await api("/faculty-requests", {
        method: "POST",
        body: JSON.stringify({ kind, email, note, ...target }),
      });
      setEmail("");
      setNote("");
      setSent(true);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="assign" onSubmit={submit}>
      <h3>{title}</h3>
      <Field label="Their university email">
        <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Note" hint="Optional. They see this with your request.">
        <input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      {sent && (
        <p className="muted" role="status">
          Request sent. If this is a faculty address, they have 7 days to answer.
        </p>
      )}
      <Button kind="secondary" type="submit" disabled={busy}>Send request</Button>
    </form>
  );
}
