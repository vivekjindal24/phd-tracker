"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { REVIEW_STATUS_LABELS } from "@/lib/types";
import type { Evaluation, ReviewCopyTrace, ReviewRow } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

type Saved = { thesisId: string; onSaved: (e: Evaluation) => void };

function InviteForm({ thesisId, onSaved }: Saved) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [institution, setInstitution] = useState("");
  const [abstract, setAbstract] = useState("");
  const [deadline, setDeadline] = useState("");
  const [allowDownload, setAllowDownload] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api(`/theses/${thesisId}/reviews`, {
        method: "POST",
        body: JSON.stringify({ name, email, institution, abstract, deadline, allow_download: allowDownload }),
      });
      onSaved(await api<Evaluation>(`/theses/${thesisId}/evaluation`));
      setOpen(false);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  if (!open) return <Button kind="secondary" onClick={() => setOpen(true)}>Invite a reviewer</Button>;
  return (
    <form className="verify" onSubmit={submit}>
      <Field label="Name"><input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Email"><input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
      <Field label="Institution"><input maxLength={200} value={institution} onChange={(e) => setInstitution(e.target.value)} /></Field>
      <Field label="Abstract" hint="Goes in the invitation, so the reviewer can decide before seeing the thesis.">
        <textarea required rows={4} maxLength={5000} value={abstract} onChange={(e) => setAbstract(e.target.value)} />
      </Field>
      <Field label="Review deadline"><input type="date" required value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
      <label className="check">
        <input type="checkbox" checked={allowDownload} onChange={(e) => setAllowDownload(e.target.checked)} />
        Allow this reviewer to download the thesis
      </label>
      <ErrorText>{error}</ErrorText>
      <div className="row">
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Sending…" : "Send invitation"}</Button>
        <Button kind="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </form>
  );
}

function ReviewerRow({ review, thesisId, onSaved }: Saved & { review: ReviewRow }) {
  const [deadline, setDeadline] = useState(review.deadline);
  const [error, setError] = useState<string | null>(null);
  const active = review.status === "invited" || review.status === "accepted";

  async function send(path: string, init: RequestInit) {
    setError(null);
    try {
      await api(path, init);
      onSaved(await api<Evaluation>(`/theses/${thesisId}/evaluation`));
    } catch (err) {
      setError(errorText(err));
    }
  }
  const patch = (body: object) => send(`/reviews/${review.id}`, { method: "PATCH", body: JSON.stringify(body) });

  return (
    <li>
      <strong>{review.name}</strong>{review.institution && ` · ${review.institution}`} · {review.email}
      <span className="badge">{REVIEW_STATUS_LABELS[review.status]}</span>
      <div className="muted">
        Due {formatDate(review.deadline)} · download {review.allow_download ? "allowed" : "off"}
        {review.decline_reason && ` · ${review.decline_reason}`}
      </div>
      {active && (
        <div className="row">
          <Field label="New deadline"><input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} /></Field>
          <Button kind="secondary" onClick={() => patch({ deadline })}>Change deadline</Button>
          <Button kind="ghost" onClick={() => patch({ allow_download: !review.allow_download })}>
            {review.allow_download ? "Turn download off" : "Allow download"}
          </Button>
        </div>
      )}
      {(review.status === "invited" || review.status === "expired") && (
        <Button kind="ghost" onClick={() => send(`/reviews/${review.id}/resend`, { method: "POST" })}>Send invitation again</Button>
      )}
      <ErrorText>{error}</ErrorText>
    </li>
  );
}

function TraceCode() {
  const [code, setCode] = useState("");
  const [trace, setTrace] = useState<ReviewCopyTrace | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setTrace(null);
    try {
      setTrace(await api<ReviewCopyTrace>(`/review-copies/${encodeURIComponent(code.trim())}`));
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <Field label="Trace a code" hint="Found on a leaked page. Every lookup is recorded.">
        <input required maxLength={9} value={code} onChange={(e) => setCode(e.target.value)} />
      </Field>
      <Button kind="secondary" type="submit">Look up</Button>
      <ErrorText>{error}</ErrorText>
      {trace && (
        <p role="status">
          {trace.reviewer_name} ({trace.reviewer_email}) · {trace.kind === "download" ? "downloaded" : "viewed"} <time dateTime={trace.issued_at}>{new Date(trace.issued_at).toLocaleString()}</time> · {trace.thesis_title}
        </p>
      )}
    </form>
  );
}

/** Exam Office only: the API sends `reviews` to no one else, names being confidential. */
export function ThesisReviewers({ thesisId, ev, onSaved }: Saved & { ev: Evaluation }) {
  return (
    <>
      <h3>Reviewers</h3>
      {ev.reviews.length === 0 ? <p className="muted">No one invited yet.</p> : (
        <ul className="plain-list">
          {ev.reviews.map((r) => <ReviewerRow key={`${r.id}-${r.deadline}`} review={r} thesisId={thesisId} onSaved={onSaved} />)}
        </ul>
      )}
      {ev.can_invite_reviewers && <InviteForm thesisId={thesisId} onSaved={onSaved} />}
      <TraceCode />
    </>
  );
}
