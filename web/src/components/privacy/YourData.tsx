"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { DownloadButton } from "@/components/DownloadButton";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import { DATA_REQUEST_KIND_LABELS } from "@/lib/types";
import type { DataRequest, DataRequestKind } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./privacy.css";

const MAX_DETAILS = 3000;

/** A person's rights over their own data (DPDP Act ss.11-13): read it, and ask to correct or
 *  erase it. The privacy officer answers; academic records the University must keep stay. */
export function YourData() {
  const requests = useFetch<DataRequest[]>("/privacy/requests/mine");
  const [kind, setKind] = useState<DataRequestKind>("correction");
  const [details, setDetails] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function ask(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSent(false);
    try {
      await api("/privacy/requests", { method: "POST", body: JSON.stringify({ kind, details }) });
      setDetails("");
      setSent(true);
      await requests.reload();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 id="your-data">Your data</h2>
      <p className="muted">
        What Anveshan keeps about you, and why, is in the <Link href="/privacy">privacy notice</Link>. Download a
        summary of it, or ask the University to correct or erase something. Records the University must keep by
        law (your academic record) cannot be erased.
      </p>
      <DownloadButton path="/privacy/my-data" from="api">Download my data</DownloadButton>
      <form className="stack-form" onSubmit={ask}>
        <Field label="Ask the University">
          <select value={kind} onChange={(e) => setKind(e.target.value as DataRequestKind)}>
            {(Object.keys(DATA_REQUEST_KIND_LABELS) as DataRequestKind[]).map((k) => (
              <option key={k} value={k}>{DATA_REQUEST_KIND_LABELS[k]}</option>
            ))}
          </select>
        </Field>
        <Field label="What should change, and why" hint="The privacy officer reads this and replies here.">
          <textarea required maxLength={MAX_DETAILS} rows={4} value={details} onChange={(e) => setDetails(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        {sent && <p role="status">Sent. You will be told when it is answered.</p>}
        <Button kind="primary" type="submit" disabled={busy || !details.trim()}>{busy ? "Sending…" : "Send request"}</Button>
      </form>
      {requests.data && requests.data.length > 0 && (
        <>
          <h3>Your requests</h3>
          <ul className="data-requests">
            {requests.data.map((r) => (
              <li key={r.id}>
                <span>
                  <strong>{DATA_REQUEST_KIND_LABELS[r.kind]}</strong> · <span className="muted">{formatWhen(r.created_at)}</span>{" "}
                  <span className={`badge ${r.status === "answered" ? "badge-approved" : ""}`}>{r.status === "answered" ? "Answered" : "Open"}</span>
                </span>
                <span>{r.details}</span>
                {r.reply && <span><strong>Reply:</strong> {r.reply}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
      <ErrorText>{requests.error}</ErrorText>
    </Card>
  );
}
