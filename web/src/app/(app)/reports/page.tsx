"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { StateBadge } from "@/components/items/StateBadge";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import { STATE_LABELS } from "@/lib/types";
import type { ItemState, ReportRow } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export default function ReportsPage() {
  const { me } = useSession();
  const [state, setState] = useState("");
  const { data, error } = useFetch<ReportRow[]>(`/reports?limit=500${state ? `&state=${state}` : ""}`);
  const isScholar = me?.scholar_id != null;

  return (
    <>
      <PageHeader
        eyebrow="Six-monthly progress"
        title="Progress reports"
        actions={isScholar && <Link href="/reports/new" className="btn btn-primary">New report</Link>}
      />
      <div className="toolbar">
        <Field label="State">
          <select value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">All</option>
            {(Object.keys(STATE_LABELS) as ItemState[]).map((s) => (
              <option key={s} value={s}>{STATE_LABELS[s]}</option>
            ))}
          </select>
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table
          label="Progress reports"
          head={["Period", "Scholar", "State", "Last change"]}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>No reports yet</h2>
              <p>{isScholar ? "Write your first six-monthly report." : "Reports appear here once scholars write them."}</p>
            </div>
          }
        >
          {data.map((r) => (
            <tr key={r.id}>
              <td>
                <Link href={`/items/progress_report/${r.id}`}>
                  {r.period.replace("-", "–")} {r.report_year}
                </Link>
              </td>
              <td>{r.scholar.name}</td>
              <td><StateBadge state={r.state} waitingOn={r.waiting_on} /></td>
              <td className="mono">{new Date(r.updated_at).toLocaleDateString()}</td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
