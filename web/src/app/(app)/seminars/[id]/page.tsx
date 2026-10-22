"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatWhen } from "@/lib/format";
import type { SeminarDetail } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../seminars.css";

export default function SeminarPage() {
  const { id } = useParams<{ id: string }>();
  const { data: s, error, setData } = useFetch<SeminarDetail>(`/seminars/${id}`);
  const [actError, setActError] = useState<string | null>(null);

  async function call(path: string, method: "POST" | "PUT", body?: unknown) {
    setActError(null);
    try {
      setData(await api<SeminarDetail>(path, { method, body: body === undefined ? undefined : JSON.stringify(body) }));
    } catch (e) {
      setActError(errorText(e));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!s) return null;
  const cancelled = s.status === "cancelled";
  return (
    <>
      <PageHeader eyebrow={`${s.unit.name} · progress seminar`} title={s.title}
        actions={cancelled ? <span className="badge badge-sent_back">Cancelled</span> : undefined} />
      <ErrorText>{actError}</ErrorText>
      <div className="seminar-detail">
        <div style={{ display: "grid", gap: "var(--space-5)" }}>
          <Card>
            <span className="seminar-when">{formatWhen(s.starts_at)}</span>
            <dl className="kv" style={{ marginTop: "var(--space-4)" }}>
              <dt>Venue</dt><dd>{s.venue || <span className="muted">To be announced</span>}</dd>
              <dt>Reviews</dt><dd>{s.period.replace("-", "–")} {s.report_year}</dd>
              <dt>Report due</dt><dd><strong>{formatDate(s.report_due)}</strong></dd>
              {s.notes && (<><dt>Notes</dt><dd>{s.notes}</dd></>)}
            </dl>
          </Card>
          <Table label="Scholars presenting"
            head={["Scholar", "Supervisor", "Progress report", ...(s.require_hardcopy ? ["Hardcopy"] : []), "Feedback"]}>
            {s.scholars.map((x) => (
              <tr key={x.scholar.id}>
                <td>
                  <Link href={`/scholars/${x.scholar.id}`}>{x.scholar.name}</Link>
                  <br /><span className="mono">{x.roll_number}</span>
                </td>
                <td>{x.supervisor ?? <span className="muted">—</span>}</td>
                <td>{x.report_state ? <StateBadge state={x.report_state} /> : <span className="badge badge-sent_back">Not started</span>}</td>
                {s.require_hardcopy && (
                  <td className="hardcopy">
                    {s.can_manage && !cancelled ? (
                      <input type="date" aria-label={`Hardcopy received from ${x.scholar.name}`}
                        value={x.hardcopy_received_on ?? ""}
                        onChange={(e) => call(`/seminars/${s.id}/hardcopy/${x.scholar.id}`, "PUT",
                          { received_on: e.target.value || null })} />
                    ) : x.hardcopy_received_on ? `Received ${formatDate(x.hardcopy_received_on)}`
                      : <span className="muted">Not received</span>}
                  </td>
                )}
                <td>
                  <Link href={`/seminars/${s.id}/review/${x.scholar.id}`}>
                    {x.finalised_at ? "View feedback" : s.is_grader ? "Grade" : "Open"}
                  </Link>
                  {x.finalised_at && <span className="badge badge-approved" style={{ marginLeft: 8 }}>Finalised</span>}
                </td>
              </tr>
            ))}
          </Table>
        </div>
        <div style={{ display: "grid", gap: "var(--space-5)" }}>
          <Card>
            <h2>Panel</h2>
            {s.panel.length === 0 ? <p className="muted">No panel named yet.</p> : (
              <ul className="panel-list">
                {s.panel.map((p) => (
                  <li key={p.faculty_id}>{p.name} {p.kind === "attending" && <span className="badge">attending</span>}</li>
                ))}
              </ul>
            )}
          </Card>
          {s.can_attend && (
            <Card>
              <h2>Attending?</h2>
              <p className="muted">Faculty attending this seminar may grade the scholars.</p>
              <Button kind="secondary" onClick={() => call(`/seminars/${s.id}/attend`, "POST").then(() =>
                api<SeminarDetail>(`/seminars/${s.id}`).then(setData))}>Join as grader</Button>
            </Card>
          )}
          {s.can_manage && !cancelled && (
            <Card>
              <h2>Manage</h2>
              <p className="muted">Cancelling notifies everyone concerned.</p>
              <Button kind="danger" onClick={() => {
                if (window.confirm("Cancel this seminar and notify everyone?")) call(`/seminars/${s.id}/cancel`, "POST");
              }}>Cancel seminar</Button>
            </Card>
          )}
          <p><Link href="/seminars">← All seminars</Link></p>
        </div>
      </div>
    </>
  );
}
