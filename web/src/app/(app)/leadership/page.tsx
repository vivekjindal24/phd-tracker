"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Owl } from "@/components/brand/Owl";
import { Card, ErrorText, PageHeader, Table } from "@/components/ui/kit";
import { formatDate } from "@/lib/format";
import type { LeadershipRow, LeadershipView } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./leadership.css";

const pct = (v: number | null) => (v === null ? "—" : `${Math.round(v * 100)}%`);

function Tiles({ t }: { t: LeadershipRow }) {
  const tiles: [string, string | number, string][] = [
    ["Current scholars", t.current, ""],
    ["Completed", t.completed, t.median_years_to_complete === null ? "time not recorded" : `median ${t.median_years_to_complete} years`],
    ["Left the programme", t.left, `drop-out rate ${pct(t.dropout_rate)}`],
    ["Supervisors at the UGC cap", `${t.supervisors_at_cap} / ${t.supervisors}`, t.average_load === null ? "" : `average load ${t.average_load}`],
  ];
  return (
    <div className="lead-tiles">
      {tiles.map(([label, value, note]) => (
        <div key={label} className="lead-tile clay">
          <span className="lead-num">{value}</span>
          <span className="lead-label">{label}</span>
          {note && <span className="muted">{note}</span>}
        </div>
      ))}
    </div>
  );
}

function Leadership() {
  const unitId = useSearchParams().get("unit");
  const { data: v, error } = useFetch<LeadershipView>(`/leadership${unitId ? `?unit_id=${unitId}` : ""}`);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;
  return (
    <>
      <PageHeader eyebrow={`Leadership view · as of ${formatDate(v.as_of)}`} title={v.unit.name} />
      <Tiles t={v.total} />
      <section className="lead-section" aria-labelledby="risk-title">
        <h2 id="risk-title">Scholars at risk <span className="badge">{v.at_risk.length}</span></h2>
        {v.at_risk.length === 0 ? (
          <Card className="empty-state"><Owl pose="cheering" size={90} /><p>No one is at risk right now.</p></Card>
        ) : (
          <Table label="Scholars at risk" head={["Scholar", "Stage", "Must submit by", "Why"]}>
            {v.at_risk.map((r) => (
              <tr key={r.scholar.id}>
                <td><Link href={`/scholars/${r.scholar.id}`}>{r.scholar.name}</Link></td>
                <td>{r.stage}</td>
                <td className="mono">{r.limit_date ? formatDate(r.limit_date) : "—"}</td>
                <td><ul className="reason-list">{r.reasons.map((x) => <li key={x}>{x}</li>)}</ul></td>
              </tr>
            ))}
          </Table>
        )}
      </section>
      {v.by_unit.length > 0 && (
        <section className="lead-section" aria-labelledby="units-title">
          <h2 id="units-title">By unit</h2>
          <Table label="By unit" head={["Unit", "Current", "Completed", "Median years", "Left", "Drop-out rate", "At cap"]}>
            {v.by_unit.map((r) => (
              <tr key={r.unit.id}>
                <td><Link href={`/leadership?unit=${r.unit.id}`}>{r.unit.name}</Link></td>
                <td className="mono">{r.current}</td>
                <td className="mono">{r.completed}</td>
                <td className="mono">{r.median_years_to_complete ?? "—"}</td>
                <td className="mono">{r.left}</td>
                <td className="mono">{pct(r.dropout_rate)}</td>
                <td className="mono">{r.supervisors_at_cap} / {r.supervisors}</td>
              </tr>
            ))}
          </Table>
        </section>
      )}
      <p className="muted">Time to completion counts from admission to the approved “degree awarded” decision in the register. Drop-outs are scholars marked as withdrawn or cancelled.</p>
    </>
  );
}

export default function LeadershipPage() {
  return (
    <Suspense>
      <Leadership />
    </Suspense>
  );
}
