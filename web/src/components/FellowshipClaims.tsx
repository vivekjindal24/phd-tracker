"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { StateBadge } from "@/components/items/StateBadge";
import { ListFoot } from "@/components/ListFoot";
import { listPath } from "@/components/ScholarFilter";
import { Button, Card, ErrorText, Field, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatMoney, formatMonth } from "@/lib/format";
import { SCHEME_LABELS } from "@/lib/types";
import type { Fellowship, FellowshipClaim, ItemView } from "@/lib/types";
import { errorText, usePagedFetch } from "@/lib/useFetch";

const yearMonth = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

/** The scholar starts a claim for one month of their fellowship; it opens as a draft to submit. */
function ClaimMonth({ first, own }: { first: Fellowship; own: Fellowship[] }) {
  const router = useRouter();
  const now = new Date();
  const [fellowshipId, setFellowshipId] = useState(first.id);
  const [month, setMonth] = useState(yearMonth(new Date(now.getFullYear(), now.getMonth() - 1, 1)));
  const [leaveDays, setLeaveDays] = useState("0");
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const chosen = own.find((f) => f.id === fellowshipId) ?? first;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const item = await api<ItemView>("/fellowship-claims", {
        method: "POST",
        body: JSON.stringify({ fellowship_id: chosen.id, month, leave_days: Number(leaveDays), note }),
      });
      router.push(`/items/fellowship_claim/${item.id}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Claim a month</h2>
      <p className="muted">
        {formatMoney(chosen.amount_monthly + chosen.hra_amount)} for the month (fellowship + HRA). It opens as a draft; once you submit it,
        it goes up the approval chain.
      </p>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          {own.length > 1 && (
            <Field label="Fellowship">
              <select value={fellowshipId} onChange={(e) => setFellowshipId(e.target.value)}>
                {own.map((f) => <option key={f.id} value={f.id}>{SCHEME_LABELS[f.scheme]}</option>)}
              </select>
            </Field>
          )}
          <Field label="Month">
            <input type="month" required pattern="\d{4}-\d{2}" placeholder="YYYY-MM" value={month}
              min={chosen.start_date.slice(0, 7)} max={yearMonth(now)} onChange={(e) => setMonth(e.target.value)} />
          </Field>
          <Field label="Days of leave taken">
            <input type="number" required min={0} max={31} step={1} value={leaveDays} onChange={(e) => setLeaveDays(e.target.value)} />
          </Field>
        </div>
        <Field label="Note" hint="Optional: anything your supervisor should know about this month.">
          <textarea value={note} maxLength={4000} onChange={(e) => setNote(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Start claim</Button>
      </form>
    </Card>
  );
}

/** Monthly claims under the fellowships list: `own` is the viewer's own active fellowships. */
export function FellowshipClaims({ own, params }: { own: Fellowship[]; params: Record<string, string> }) {
  const [sort, setSort] = useState("");
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<FellowshipClaim>(listPath("/fellowship-claims", params, { sort }), 200);

  return (
    <section aria-labelledby="claims-heading" className="card-gap">
      <h2 id="claims-heading">Monthly claims</h2>
      {own[0] && <ClaimMonth first={own[0]} own={own} />}
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Monthly fellowship claims" head={["Month", "Scholar", "Amount", "Leave", "Status"]}
          sort={{ by: sort, keys: ["month", "scholar", "amount", null, "state"], onChange: setSort }}
          empty={<p className="muted">No claims yet.</p>}>
          {data.map((c) => (
            <tr key={c.id}>
              <td><Link href={`/items/fellowship_claim/${c.id}`}>{formatMonth(c.month)}</Link></td>
              <td>{c.scholar.name}<div className="muted">{SCHEME_LABELS[c.scheme]}</div></td>
              <td className="mono">{formatMoney(c.amount)}</td>
              <td>{c.leave_days} {c.leave_days === 1 ? "day" : "days"}</td>
              <td><StateBadge state={c.state} waitingOn={c.waiting_on} /></td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </section>
  );
}
