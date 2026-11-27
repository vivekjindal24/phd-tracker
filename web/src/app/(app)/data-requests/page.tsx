"use client";

import { useState } from "react";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { NotForYourRole } from "@/components/ui/RequireRole";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import { DATA_REQUEST_KIND_LABELS } from "@/lib/types";
import type { DataRequest } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "@/components/privacy/privacy.css";

function Answer({ request, onDone }: { request: DataRequest; onDone: () => Promise<void> }) {
  const [reply, setReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function send() {
    setBusy(true);
    setError(null);
    try {
      await api(`/privacy/requests/${request.id}/answer`, { method: "POST", body: JSON.stringify({ reply }) });
      await onDone();
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <div className="stack-form">
      <Field label="Reply" hint="Say what was done, or why it cannot be (for example, a record the University must keep).">
        <textarea rows={3} maxLength={3000} value={reply} onChange={(e) => setReply(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="primary" disabled={busy || !reply.trim()} onClick={send}>{busy ? "Sending…" : "Send reply"}</Button>
    </div>
  );
}

/** Requests about personal data, for the privacy officer (the root admins until one is named).
 *  A correction is made where the record lives — usually by the admin over the person's unit. */
export default function DataRequestsPage() {
  const { me } = useSession();
  const list = useFetch<DataRequest[]>(me?.answers_data_requests ? "/privacy/requests" : null);
  if (!me) return null;
  if (!me.answers_data_requests) return <NotForYourRole />;
  const open = list.data?.filter((r) => r.status === "open") ?? [];
  const answered = list.data?.filter((r) => r.status === "answered") ?? [];

  return (
    <>
      <PageHeader eyebrow="Privacy" title="Data requests" />
      <ErrorText>{list.error}</ErrorText>
      <Card>
        <h2>Waiting for a reply <span className="badge">{open.length}</span></h2>
        {open.length === 0 ? <p className="muted">Nothing waiting.</p> : (
          <ul className="data-requests">
            {open.map((r) => (
              <li key={r.id}>
                <span><strong>{r.requester}</strong> · {DATA_REQUEST_KIND_LABELS[r.kind]} · <span className="muted">{formatWhen(r.created_at)}</span></span>
                <span>{r.details}</span>
                <Answer request={r} onDone={list.reload} />
              </li>
            ))}
          </ul>
        )}
      </Card>
      {answered.length > 0 && (
        <Card>
          <h2>Answered</h2>
          <ul className="data-requests">
            {answered.map((r) => (
              <li key={r.id}>
                <span><strong>{r.requester}</strong> · {DATA_REQUEST_KIND_LABELS[r.kind]} · <span className="muted">answered {r.answered_at && formatWhen(r.answered_at)}</span></span>
                <span>{r.details}</span>
                <span><strong>Reply:</strong> {r.reply}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
