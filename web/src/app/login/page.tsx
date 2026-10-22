"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import "./login.css";

function LoginForm() {
  const { me, login } = useSession();
  const router = useRouter();
  const expired = useSearchParams().get("expired") === "1";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(expired ? "Your session ended. Please log in again." : null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (me) router.replace("/home");
  }, [me, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login-card clay" onSubmit={submit} aria-labelledby="login-title">
      <h2 id="login-title">Log in</h2>
      <Field label="Email">
        <input type="email" autoComplete="username" required value={email}
          onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password">
        <input type="password" autoComplete="current-password" required value={password}
          onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="primary" type="submit" disabled={busy}>
        {busy ? "Logging in…" : "Log in"}
      </Button>
      <p className="login-help">Forgot your password? Ask your department&apos;s PhD coordinator.</p>
    </form>
  );
}

export default function LoginPage() {
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
        <p className="login-tagline">Your research, every step — from first meeting to degree.</p>
        <Owl pose="reading" size={220} />
      </section>
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
