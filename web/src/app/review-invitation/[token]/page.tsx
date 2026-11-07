"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { UniversityMark } from "@/components/brand/UniversityMark";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ReviewInvitation } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "@/components/ui/ui.css";
import "@/app/review/review.css";

type Accepted = { has_password: boolean; email_sent: boolean };

function acceptedText(a: Accepted): string {
  if (a.has_password) return "Thank you. Log in with your existing password to start your review.";
  if (a.email_sent) return "Thank you. We have emailed you a link to set your password.";
  return "Thank you. We could not send the email, so please use “Forgot your password?” on the login page.";
}

export default function InvitationPage() {
  const { token } = useParams<{ token: string }>();
  const path = `/review-invitations/${encodeURIComponent(token)}`;
  const { data, error } = useFetch<ReviewInvitation>(path);
  const [noConflict, setNoConflict] = useState(false);
  const [confidential, setConfidential] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [done, setDone] = useState<string | null>(null);
  const [actError, setActError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(run: () => Promise<string>) {
    setBusy(true);
    setActError(null);
    try {
      setDone(await run());
    } catch (e) {
      setActError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const accept = () => send(async () => acceptedText(await api<Accepted>(`${path}/accept`, {
    method: "POST",
    body: JSON.stringify({ no_conflict: noConflict, confidential }),
  })));
  const decline = () => send(async () => {
    await api(`${path}/decline`, { method: "POST", body: JSON.stringify({ reason }) });
    return "Thank you for letting us know.";
  });

  if (error) {
    return (
      <main className="empty-state">
        <UniversityMark />
        <Owl pose="empty" size={110} />
        <h1>This invitation is not available</h1>
        <p role="alert">It may have expired or already been answered. Please contact the university's Exam Office.</p>
      </main>
    );
  }
  if (!data) return null;
  if (done) {
    return (
      <main className="empty-state">
        <UniversityMark />
        <Owl pose="reading" size={110} />
        <p role="status">{done}</p>
        <Link href="/login">Go to log in</Link>
      </main>
    );
  }
  return (
    <main className="review-shell">
      <UniversityMark />
      <Card>
        <h1>Invitation to review a PhD thesis</h1>
        <p>Dear {data.reviewer_name}, {data.university} invites you to review this thesis.</p>
        <h2>{data.thesis_title}</h2>
        <p>{data.abstract}</p>
        <p><strong>Review deadline:</strong> {formatDate(data.deadline)}</p>
        <label className="review-check">
          <input type="checkbox" checked={noConflict} onChange={(e) => setNoConflict(e.target.checked)} />
          I have no conflict of interest with the scholar or their supervisors.
        </label>
        <label className="review-check">
          <input type="checkbox" checked={confidential} onChange={(e) => setConfidential(e.target.checked)} />
          I will keep this thesis confidential and not share it. I understand each copy is uniquely marked and traceable to me.
        </label>
        <ErrorText>{actError}</ErrorText>
        {declining ? (
          <>
            <Field label="Reason (optional)"><textarea rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <div className="row">
              <Button kind="primary" disabled={busy} onClick={decline}>Confirm decline</Button>
              <Button kind="ghost" onClick={() => setDeclining(false)}>Go back</Button>
            </div>
          </>
        ) : (
          <div className="row">
            <Button kind="primary" disabled={busy || !noConflict || !confidential} onClick={accept}>Accept</Button>
            <Button kind="ghost" onClick={() => setDeclining(true)}>Decline</Button>
          </div>
        )}
      </Card>
    </main>
  );
}
