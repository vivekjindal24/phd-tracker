"use client";

import { useState } from "react";
import { PersonPicker } from "@/components/PersonPicker";
import { SignatureCard } from "@/components/SignatureCard";
import { Button, Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { RequireRole } from "@/components/ui/RequireRole";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import type { PendingSignature } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

type Person = { id: string; full_name: string; email: string };

/** Keepers' page (PRD F17b): confirm signatures people uploaded, and hand in paper ones. */
export default function SignaturesPage() {
  return (
    <RequireRole roles={["admin", "research_office"]}>
      <Signatures />
    </RequireRole>
  );
}

function Signatures() {
  const pending = useFetch<PendingSignature[]>("/signatures/pending");
  const [person, setPerson] = useState<Person | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function confirm(userId: string) {
    setError(null);
    try {
      await api(`/users/${userId}/signature/confirm`, { method: "POST" });
      await pending.reload();
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <>
      <PageHeader title="Signatures" />
      <Card>
        <h2>Waiting for you to confirm</h2>
        <p className="muted">Check each against the person’s wet signature before confirming. Once confirmed, it is stamped on what they sign.</p>
        {pending.data?.length === 0 && <p className="muted">Nothing waiting.</p>}
        <ul className="signature-queue">
          {pending.data?.map((p) => (
            <li key={p.user_id}>
              <img className="signature-specimen" src={p.signature.image} alt={`Signature of ${p.full_name}`} />
              <div>
                <strong>{p.full_name}</strong> <span className="muted">{p.email}</span>
                <div className="muted">Uploaded {formatWhen(p.signature.uploaded_at)}</div>
              </div>
              <Button kind="primary" onClick={() => confirm(p.user_id)}>Confirm</Button>
            </li>
          ))}
        </ul>
        <ErrorText>{error ?? pending.error}</ErrorText>
      </Card>
      <div className="card-gap">
        <Card>
          <h2>Hand in a paper signature</h2>
          <p className="muted">For someone who signed on paper at the department: choose them, then upload the scan or photo.</p>
          <PersonPicker<Person> label="Person" path="/users" value={person} onPick={setPerson} detail={(p) => p.email} />
        </Card>
      </div>
      {person && (
        <div className="card-gap">
          <SignatureCard key={person.id} userId={person.id} self={false} onChange={pending.reload} />
        </div>
      )}
    </>
  );
}
