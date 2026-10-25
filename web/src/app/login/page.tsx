"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { api, ApiError, exchangeSsoCode, ssoStartUrl } from "@/lib/api";
import { useSession } from "@/lib/session";
import { useFetch } from "@/lib/useFetch";
import "./login.css";

const SSO_LABELS: Record<string, string> = { google: "Google", microsoft: "Microsoft" };
const SSO_FAILED = "Signing in with your university account failed. Please try again.";
const SSO_ERRORS: Record<string, string> = {
  no_account: "There is no Anveshan account for this email — ask your department admin.",
  domain_not_allowed: "Please use your university email account.",
  no_verified_email: "Your account did not share a verified email address.",
  cancelled: "Sign-in was cancelled.",
  expired: "That sign-in took too long. Please try again.",
};

function initialMessage(params: URLSearchParams): string | null {
  if (params.get("expired") === "1") return "Your session ended. Please log in again.";
  const sso = params.get("sso_error");
  return sso ? (SSO_ERRORS[sso] ?? SSO_FAILED) : null;
}

function ForgotPassword({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login-card clay" onSubmit={submit} aria-labelledby="forgot-title">
      <h2 id="forgot-title">Reset your password</h2>
      {sent ? (
        <p role="status">If an account exists for <strong>{email}</strong>, a link to set a new password is on its way. It works once, for 72 hours.</p>
      ) : (
        <>
          <Field label="Email">
            <input type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} />
          </Field>
          <ErrorText>{error}</ErrorText>
          <Button kind="primary" type="submit" disabled={busy}>{busy ? "Sending…" : "Email me a link"}</Button>
        </>
      )}
      <Button kind="ghost" onClick={onBack}>← Back to log in</Button>
    </form>
  );
}

function LoginForm() {
  const { me, login, reload } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const ssoCode = params.get("sso_code");
  const { data: providers } = useFetch<string[]>("/auth/sso/providers");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(() => initialMessage(params));
  const [busy, setBusy] = useState(ssoCode !== null);
  const [forgot, setForgot] = useState(false);

  useEffect(() => {
    if (me) router.replace("/home");
  }, [me, router]);

  // Back from the university's sign-in page: trade the one-time code for a session.
  useEffect(() => {
    if (!ssoCode) return;
    exchangeSsoCode(ssoCode)
      .then(reload)
      .then(() => router.replace("/home"))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : SSO_FAILED);
        setBusy(false);
        router.replace("/login");
      });
  }, [ssoCode, reload, router]);

  if (forgot) return <ForgotPassword onBack={() => setForgot(false)} />;

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
      <Button kind="ghost" onClick={() => setForgot(true)}>Forgot your password?</Button>
      {providers && providers.length > 0 && (
        <div className="login-sso" aria-label="Or sign in with your university account">
          <span className="login-or">or</span>
          {providers.map((p) => (
            <a key={p} className="btn btn-secondary" href={ssoStartUrl(p)}>
              Continue with {SSO_LABELS[p] ?? p}
            </a>
          ))}
        </div>
      )}
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
        <Link className="login-brand" href="/">
          <OwlMark size={52} />
          <h1 id="brand">Anveshan</h1>
        </Link>
        <p className="login-tagline">Your research, every step — from first meeting to degree.</p>
        <Owl pose="reading" size={220} />
      </section>
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
