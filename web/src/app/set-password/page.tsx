"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import type { FormEvent } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { setPasswordWithLink } from "@/lib/api";
import { useSession } from "@/lib/session";
import { errorText } from "@/lib/useFetch";
import "../login/login.css";

const MIN_LENGTH = 10;

function SetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const { reload } = useSession();
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("The two passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await setPasswordWithLink(token, password);
      await reload();
      router.replace("/home");
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  if (!token) {
    return (
      <div className="login-card clay">
        <h2>This link is incomplete</h2>
        <p>Open the link from your email again, or ask for a new one.</p>
        <Link href="/login" className="btn btn-secondary">Go to log in</Link>
      </div>
    );
  }
  return (
    <form className="login-card clay" onSubmit={submit} aria-labelledby="set-title">
      <h2 id="set-title">Choose your password</h2>
      <Field label="New password" hint={`At least ${MIN_LENGTH} characters.`}>
        <input type="password" autoComplete="new-password" required minLength={MIN_LENGTH} maxLength={200}
          value={password} onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <Field label="Type it again">
        <input type="password" autoComplete="new-password" required minLength={MIN_LENGTH} maxLength={200}
          value={confirm} onChange={(e) => setConfirm(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save and log in"}</Button>
      <Link href="/login" className="login-help">Back to log in</Link>
    </form>
  );
}

export default function SetPasswordPage() {
  return (
    <main className="login">
      <div className="login-theme">
        <ThemeToggle />
      </div>
      <section className="login-hero" aria-labelledby="brand">
        <div className="login-brand">
          <OwlMark size={52} />
          <h1 id="brand">Anveshan</h1>
        </div>
        <p className="login-tagline">Welcome. One step and you are in.</p>
        <Owl pose="reading" size={220} />
      </section>
      <Suspense>
        <SetPasswordForm />
      </Suspense>
    </main>
  );
}
