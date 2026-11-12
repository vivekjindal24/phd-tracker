"use client";

import Link from "next/link";
import { useState } from "react";
import { ScholarSearch } from "@/components/ScholarSearch";
import { Button, ErrorText, Field, PageHeader, ShowMore, Table } from "@/components/ui/kit";
import { RequireRole } from "@/components/ui/RequireRole";
import { formatWhen } from "@/lib/format";
import { ROLE_LABELS } from "@/lib/types";
import type { AuditRow, Role, Scholar } from "@/lib/types";
import { usePagedFetch } from "@/lib/useFetch";

const ACTIONS: Record<AuditRow["action"], string> = {
  insert: "Added",
  update: "Changed",
  soft_delete: "Removed",
  restore: "Restored",
  transition: "Moved",
  lookup: "Looked up",
};
const words = (s: string) => s.replace(/_/g, " ");

/** What happened, in a sentence: never the values, which the API does not send. */
function describe(r: AuditRow): string {
  if (r.action === "transition") return `${words(r.from_state ?? "")} → ${words(r.to_state ?? "")}`;
  if (r.action === "update" && r.fields.length) return r.fields.map(words).join(", ");
  return "";
}

function AuditLog() {
  const [scholar, setScholar] = useState<Scholar | null>(null);
  const [action, setAction] = useState("");
  const [table, setTable] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState("");
  const params = new URLSearchParams();
  if (scholar) params.set("scholar_id", scholar.id);
  if (action) params.set("action", action);
  if (table.trim()) params.set("table_name", table.trim().toLowerCase().replace(/ /g, "_"));
  if (from) params.set("date_from", from);
  if (to) params.set("date_to", to);
  if (sort) params.set("sort", sort);
  const { data, error, hasMore, more } = usePagedFetch<AuditRow>(`/audit-log?${params}`, 100);

  return (
    <>
      <PageHeader eyebrow="Compliance" title="Audit log" />
      <p className="muted">Who added, changed, removed or moved which record, and when. The contents of a record are never shown here; open the record itself to read them.</p>
      <div className="toolbar">
        {scholar ? (
          <Field label="Scholar">
            <Button kind="ghost" onClick={() => setScholar(null)}>{scholar.full_name} ×</Button>
          </Field>
        ) : (
          <ScholarSearch label="Scholar" onPick={setScholar} />
        )}
        <Field label="What happened">
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">Anything</option>
            {(Object.keys(ACTIONS) as AuditRow["action"][]).map((a) => <option key={a} value={a}>{ACTIONS[a]}</option>)}
          </select>
        </Field>
        <Field label="Kind of record" hint="For example: meetings, milestones, users">
          <input value={table} maxLength={60} onChange={(e) => setTable(e.target.value)} />
        </Field>
        <Field label="From"><input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        <Field label="To"><input type="date" min={from} value={to} onChange={(e) => setTo(e.target.value)} /></Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Audit log" head={["When", "Who", "What", "Record", "Scholar", "Detail"]}
          sort={{ by: sort, keys: ["when", "who", "what", "record", null, null], onChange: setSort }}
          empty={<div className="empty-state"><h2>Nothing matches</h2><p>Try a wider date range or fewer filters.</p></div>}>
          {data.map((r) => (
            <tr key={r.id}>
              <td className="mono">{formatWhen(r.at)}</td>
              <td>
                {r.actor ?? <span className="muted">System</span>}
                {r.actor_roles.length > 0 && <span className="muted"> · {r.actor_roles.map((x) => ROLE_LABELS[x as Role] ?? x).join(", ")}</span>}
              </td>
              <td>{ACTIONS[r.action]}</td>
              <td>{words(r.table_name)}</td>
              <td>{r.scholar ? <Link href={`/scholars/${r.scholar.id}`}>{r.scholar.name}</Link> : <span className="muted">—</span>}</td>
              <td>{describe(r)}</td>
            </tr>
          ))}
        </Table>
      )}
      <ShowMore hasMore={hasMore} more={more} />
    </>
  );
}

export default function AuditPage() {
  return <RequireRole roles={["admin", "research_office", "vice_chancellor"]}><AuditLog /></RequireRole>;
}
