"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { HEAD_LABELS } from "@/lib/types";
import type { LedgerHead, LedgerKind, LedgerView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./ledger.css";

type Owner = { project_id: string } | { fellowship_id: string };

function AddEntry({ owner, view, onSaved }: { owner: Owner; view: LedgerView; onSaved: (v: LedgerView) => void }) {
  const isFellowship = "fellowship_id" in owner;
  const [kind, setKind] = useState<LedgerKind>(view.can_manage ? "disbursement" : "expense");
  const [head, setHead] = useState<LedgerHead>(isFellowship ? "fellowship_salary" : "equipment");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<LedgerView>("/ledger", {
        method: "POST",
        body: JSON.stringify({ ...owner, entry_kind: kind, head, amount: Number(amount), entry_date: date, reference: reference || null }),
      }));
      setAmount("");
      setReference("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ledger-add" onSubmit={submit}>
      <div className="row">
        <Field label="Entry">
          <select value={kind} onChange={(e) => setKind(e.target.value as LedgerKind)} disabled={!view.can_manage}>
            <option value="disbursement">Money received</option>
            <option value="expense">Expense</option>
          </select>
        </Field>
        <Field label="Head">
          <select value={head} onChange={(e) => setHead(e.target.value as LedgerHead)}>
            {(Object.keys(HEAD_LABELS) as LedgerHead[]).map((h) => <option key={h} value={h}>{HEAD_LABELS[h]}</option>)}
          </select>
        </Field>
        <Field label="Amount (₹)">
          <input type="number" required min={0.01} step={0.01} value={amount} onChange={(e) => setAmount(e.target.value)} />
        </Field>
        <Field label="Date"><input type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      </div>
      <Field label="Reference" hint="Sanction letter, voucher or bill number (optional)">
        <input maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit" disabled={busy}>{busy ? "Saving…" : "Add entry"}</Button>
    </form>
  );
}

/** Money in and out with a running balance (PRD M8). The API decides who sees it and who may
 *  add: offices and admins everything, the PI expenses on their own project. */
export function Ledger({ owner }: { owner: Owner }) {
  const path = "project_id" in owner ? `/projects/${owner.project_id}/ledger` : `/fellowships/${owner.fellowship_id}/ledger`;
  const { data, error, setData } = useFetch<LedgerView>(path);
  const [actError, setActError] = useState<string | null>(null);

  async function remove(id: string) {
    setActError(null);
    try {
      setData(await api<LedgerView>(`/ledger/${id}`, { method: "DELETE" }));
    } catch (err) {
      setActError(errorText(err));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!data) return null;
  return (
    <div className="ledger">
      <dl className="ledger-totals">
        {data.sanctioned !== null && <div><dt>Sanctioned</dt><dd className="mono">{formatMoney(data.sanctioned)}</dd></div>}
        <div><dt>Received</dt><dd className="mono">{formatMoney(data.received)}</dd></div>
        <div><dt>Spent</dt><dd className="mono">{formatMoney(data.spent)}</dd></div>
        <div className={data.balance < 0 ? "ledger-negative" : undefined}><dt>Balance</dt><dd className="mono">{formatMoney(data.balance)}</dd></div>
      </dl>
      <Table label="Ledger" head={["Date", "Entry", "Head", "Amount", "Balance", ""]}
        empty={<p className="muted ledger-empty">No entries yet.</p>}>
        {data.entries.map((e) => (
          <tr key={e.id}>
            <td className="mono">{formatDate(e.entry_date)}</td>
            <td>{e.entry_kind === "disbursement" ? "Received" : "Expense"}{e.reference && <div className="muted">{e.reference}</div>}</td>
            <td>{HEAD_LABELS[e.head]}</td>
            <td className={`mono ${e.entry_kind === "expense" ? "ledger-out" : "ledger-in"}`}>{e.entry_kind === "expense" ? "−" : "+"}{formatMoney(e.amount)}</td>
            <td className="mono">{formatMoney(e.balance)}</td>
            <td>{data.can_manage && <Button kind="ghost" aria-label={`Remove entry of ${formatMoney(e.amount)} on ${formatDate(e.entry_date)}`} onClick={() => remove(e.id)}>Remove</Button>}</td>
          </tr>
        ))}
      </Table>
      <ErrorText>{actError}</ErrorText>
      {(data.can_manage || data.can_add_expense) && <AddEntry owner={owner} view={data} onSaved={setData} />}
    </div>
  );
}
