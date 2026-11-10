"use client";

import { type FormEvent, useState } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/types";
import type { OfficeRole } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

type Holder = { id: string; role: OfficeRole; user_id: string; full_name: string; email: string };
type FoundUser = { id: string; email: string };

const OFFICES: { role: OfficeRole; hint: string }[] = [
  { role: "vice_chancellor", hint: "Reads the whole university and decides wherever an approval chain names the Vice Chancellor." },
  { role: "research_office", hint: "Final approvals, the committee register, admissions and grants." },
  { role: "exam_office", hint: "Coursework grades, thesis receipt, examiners and the viva." },
  { role: "library", hint: "Publication checks, plagiarism score and the Shodhganga deposit." },
];

/** Who holds each university-wide role. Appointing is the root admin's alone; the API re-checks. */
export function Offices({ emailConfigured }: { emailConfigured: boolean }) {
  const { data: holders, error: loadError, reload } = useFetch<Holder[]>("/office-holders");
  const [role, setRole] = useState<OfficeRole>("vice_chancellor");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(work: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await reload();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  function appoint(e: FormEvent) {
    e.preventDefault();
    run(async () => {
      const wanted = email.trim().toLowerCase();
      const found = await api<FoundUser[]>(`/users?q=${encodeURIComponent(wanted)}&limit=5`);
      let user = found.find((u) => u.email.toLowerCase() === wanted);
      if (!user) {
        if (!name.trim()) throw new Error("Nobody has this email yet. Add their full name to create the account.");
        user = await api<FoundUser>("/users", {
          method: "POST",
          body: JSON.stringify({ email: wanted, full_name: name, password: emailConfigured ? null : password }),
        });
      }
      await api("/role-assignments", { method: "POST", body: JSON.stringify({ user_id: user.id, role }) });
      setEmail("");
      setName("");
      setPassword("");
    });
  }

  return (
    <Card className="settings-chains">
      <h2>University offices</h2>
      <p className="muted">These roles cover the whole university. A person may hold more than one.</p>
      <ErrorText>{loadError ?? error}</ErrorText>
      <ul className="chain-list">
        {OFFICES.map((o) => {
          const mine = (holders ?? []).filter((h) => h.role === o.role);
          return (
            <li key={o.role} className="chain">
              <h3>{ROLE_LABELS[o.role]}</h3>
              <p className="muted">{o.hint}</p>
              {mine.length === 0 && holders && <p className="muted">Nobody appointed yet.</p>}
              <ol className="chain-steps">
                {mine.map((h) => (
                  <li key={h.id} className="chain-step">
                    <span>{h.full_name} · {h.email}</span>
                    <span className="chain-step-actions">
                      <button type="button" disabled={busy} aria-label={`Remove ${h.full_name} from ${ROLE_LABELS[o.role]}`}
                        onClick={() => run(() => api(`/role-assignments/${h.id}`, { method: "DELETE" }))}>×</button>
                    </span>
                  </li>
                ))}
              </ol>
            </li>
          );
        })}
      </ul>
      <form className="offices-form" onSubmit={appoint}>
        <h3>Appoint someone</h3>
        <p className="muted">Type their email. Add a full name only for someone with no account yet.</p>
        <div className="row">
          <Field label="Office">
            <select value={role} onChange={(e) => setRole(e.target.value as OfficeRole)}>
              {OFFICES.map((o) => <option key={o.role} value={o.role}>{ROLE_LABELS[o.role]}</option>)}
            </select>
          </Field>
          <Field label="Email">
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <Field label="Full name">
            <input maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          {!emailConfigured && (
            <Field label="Initial password" hint="For a new account: at least 10 characters. Email isn't set up, so no link can be sent.">
              <input type="text" minLength={10} value={password} autoComplete="new-password"
                onChange={(e) => setPassword(e.target.value)} />
            </Field>
          )}
        </div>
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Appoint"}</Button>
      </form>
    </Card>
  );
}
