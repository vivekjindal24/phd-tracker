"use client";

import { type FormEvent, useState } from "react";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { StandInCard } from "@/components/StandInCard";
import { api, logout } from "@/lib/api";
import { useSession } from "@/lib/session";
import { errorText } from "@/lib/useFetch";

const MIN_LENGTH = 10; // the API's Password rule; the API re-checks

export default function AccountPage() {
  const { me } = useSession();
  const [current, setCurrent] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) return setError("The two new passwords do not match.");
    setBusy(true);
    setError(null);
    try {
      await api("/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: password }),
      });
      // The API has logged every device out: clear this one too and start again at log in.
      await logout();
      window.location.assign("/login?password_set=1");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow={me?.email} title="My account" />
      <Card>
        <form className="stack-form" onSubmit={submit} aria-labelledby="password-title">
          <h2 id="password-title">Change your password</h2>
          <p className="muted">Saving logs you out on every device; log in again with the new password.</p>
          <Field label="Current password">
            <input type="password" autoComplete="current-password" required maxLength={200}
              value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <Field label="New password" hint={`At least ${MIN_LENGTH} characters.`}>
            <input type="password" autoComplete="new-password" required minLength={MIN_LENGTH} maxLength={200}
              value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          <Field label="Type the new password again">
            <input type="password" autoComplete="new-password" required minLength={MIN_LENGTH} maxLength={200}
              value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          <ErrorText>{error}</ErrorText>
          <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save new password"}</Button>
        </form>
      </Card>
      {me?.faculty_id && <div className="card-gap"><StandInCard /></div>}
    </>
  );
}
