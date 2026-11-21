"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { ItemView, SupervisorChangeContent } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

/** A proposed change of supervisor: it takes effect only on the final approval. Its author may
 *  withdraw it while it is a draft or sent back, and propose again. */
export function SupervisorChangeDetails({ item }: { item: ItemView }) {
  const c = item.content as SupervisorChangeContent;
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  async function withdraw() {
    setError(null);
    try {
      await api(`/supervisor-changes/${item.id}`, { method: "DELETE" });
      router.push(`/scholars/${c.scholar_id}`);
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <Card>
      <h2>Change of supervisor</h2>
      <dl className="kv">
        <dt>Scholar</dt><dd><Link href={`/scholars/${c.scholar_id}`}>{item.scholar.name}</Link></dd>
        <dt>From</dt><dd>{c.from?.name ?? <span className="muted">No supervisor</span>}</dd>
        <dt>To</dt><dd><strong>{c.to.name}</strong></dd>
        <dt>Reason</dt><dd className="prose">{c.reason}</dd>
        <dt>Scholar&apos;s consent</dt><dd>{c.scholar_consent ? "Given" : "Not recorded"}</dd>
        {c.order_ref && <><dt>Order</dt><dd>{c.order_ref}</dd></>}
        <dt>From the day</dt>
        <dd>{c.effective_on ? formatDate(c.effective_on) : <span className="muted">The day it is approved</span>}</dd>
      </dl>
      <p className="muted">
        {item.state === "approved"
          ? "Approved: the change has taken effect and is in the scholar's supervision history."
          : "The supervisor changes only once this is approved."}
      </p>
      <ErrorText>{error}</ErrorText>
      {item.can_edit && <Button kind="ghost" onClick={withdraw}>Withdraw this proposal</Button>}
    </Card>
  );
}
