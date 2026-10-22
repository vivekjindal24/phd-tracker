"use client";

import Link from "next/link";
import { Owl } from "@/components/brand/Owl";
import { ErrorText, PageHeader, Table } from "@/components/ui/kit";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { Meeting } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./meetings.css";

export default function MeetingsPage() {
  const { me } = useSession();
  const { data, error } = useFetch<Meeting[]>("/meetings?limit=200");
  const canLog = me?.roles.some((r) => r === "scholar" || r === "supervisor") ?? false;

  return (
    <>
      <PageHeader
        eyebrow="Supervision trail"
        title="Meetings"
        actions={canLog && <Link href="/meetings/new" className="btn btn-primary">Log meeting</Link>}
      />
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table
          label="Meetings"
          head={["Date", "Scholar", "Supervisor", "Agenda"]}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>No meetings yet</h2>
              <p>Log the first one to start the supervision trail.</p>
            </div>
          }
        >
          {data.map((m) => (
            <tr key={m.id}>
              <td className="mono">
                <Link href={`/meetings/${m.id}`}>{formatDate(m.meeting_date)}</Link>
              </td>
              <td>{m.scholar.name}</td>
              <td>{m.supervisor.name}</td>
              <td>
                {m.redacted ? <span className="redacted">Meeting held · minutes not shared</span>
                  : m.agenda}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
