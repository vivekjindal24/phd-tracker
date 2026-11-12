"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { QueueEntry } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const STUCK_DAYS = 14; // PRD F10: items stuck longer than this are flagged

const keyOf = (q: QueueEntry) => `${q.item_type}/${q.id}`;
type Outcome = { approved: number; failed: { entry: QueueEntry; reason: string }[] };

export default function QueuePage() {
  const { data, error, reload } = useFetch<QueueEntry[]>("/queue");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [outcome, setOutcome] = useState<Outcome | null>(null);

  // The queue is one unpaged response of the caller's own steps, so it is filtered here.
  const needle = q.trim().toLowerCase();
  const visible = (data ?? []).filter(
    (e) => (!type || e.label === type) && (!needle || `${e.scholar.name} ${e.title}`.toLowerCase().includes(needle)),
  );
  const quick = visible.filter((e) => e.quick_approve);
  const chosen = quick.filter((e) => selected.has(keyOf(e)));
  const filtered = Boolean(type || needle);

  const toggle = (k: string) =>
    setSelected((s) => (s.has(k) ? new Set([...s].filter((x) => x !== k)) : new Set([...s, k])));

  // One call per item through the same endpoint as the item page, so every server rule holds.
  async function approveChosen() {
    setConfirming(false);
    const failed: Outcome["failed"] = [];
    for (const [i, entry] of chosen.entries()) {
      setProgress(i + 1);
      try {
        await api(`/items/${entry.item_type}/${entry.id}/approve`, { method: "POST" });
      } catch (e) {
        failed.push({ entry, reason: errorText(e) });
      }
    }
    setProgress(null);
    setOutcome({ approved: chosen.length - failed.length, failed });
    setSelected(new Set());
    await reload();
  }

  const busy = progress !== null;
  return (
    <>
      <PageHeader eyebrow="Waiting for you" title="Your queue" />
      <ErrorText>{error}</ErrorText>
      {data && data.length > 0 && (
        <div className="toolbar">
          <Field label="Type">
            <select value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">All</option>
              {[...new Set(data.map((e) => e.label))].sort().map((l) => <option key={l}>{l}</option>)}
            </select>
          </Field>
          <Field label="Search">
            <input type="search" placeholder="Scholar or title" value={q} onChange={(e) => setQ(e.target.value)} />
          </Field>
        </div>
      )}
      {outcome && (
        <div role="status" className="bulk-outcome">
          <p>Approved {outcome.approved} item{outcome.approved === 1 ? "" : "s"}.</p>
          {outcome.failed.length > 0 && (
            <ul className="error-text">
              {outcome.failed.map(({ entry, reason }) => (
                <li key={keyOf(entry)}>{entry.label} · {entry.title} ({entry.scholar.name}): {reason}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {quick.length > 0 && (
        <div className="bulk-bar">
          {busy ? (
            <p role="status">Approving {progress} of {chosen.length}…</p>
          ) : confirming ? (
            <>
              <p>Approve {chosen.length} item{chosen.length === 1 ? "" : "s"} with no comment? Each moves to its next step.</p>
              <Button kind="primary" onClick={approveChosen}>Approve {chosen.length}</Button>
              <Button kind="ghost" onClick={() => setConfirming(false)}>Cancel</Button>
            </>
          ) : (
            <>
              <Button kind="ghost" onClick={() => setSelected(new Set(quick.map(keyOf)))}>Select all {quick.length}</Button>
              <Button kind="primary" disabled={chosen.length === 0} onClick={() => { setOutcome(null); setConfirming(true); }}>
                Approve selected{chosen.length ? ` (${chosen.length})` : ""}
              </Button>
              {quick.length < visible.length && (
                <p className="muted">Items without a box need something from you first, such as a rating — open them one by one.</p>
              )}
            </>
          )}
        </div>
      )}
      {data && (
        <Table
          label="Items waiting for your decision"
          head={["Select", "Item", "Scholar", "Your step", "Waiting"]}
          empty={
            filtered ? (
              <p className="empty-state">No waiting item matches the filter.</p>
            ) : (
              <div className="empty-state">
                <Owl pose="cheering" size={96} />
                <h2>All caught up</h2>
                <p>Nothing is waiting for your decision.</p>
              </div>
            )
          }
        >
          {visible.map((e) => (
            <tr key={keyOf(e)}>
              <td>
                {e.quick_approve && (
                  <input type="checkbox" className="bulk-check" disabled={busy || confirming}
                    aria-label={`Select ${e.label} · ${e.title}, ${e.scholar.name}`}
                    checked={selected.has(keyOf(e))} onChange={() => toggle(keyOf(e))} />
                )}
              </td>
              <td><Link href={`/items/${e.item_type}/${e.id}`}>{e.label} · {e.title}</Link></td>
              <td>{e.scholar.name}</td>
              <td>{e.step}</td>
              <td>
                <span className={`badge ${e.days_waiting > STUCK_DAYS ? "badge-sent_back" : ""}`}>
                  {e.days_waiting === 0 ? "Today" : `${e.days_waiting} day${e.days_waiting === 1 ? "" : "s"}`}
                </span>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
