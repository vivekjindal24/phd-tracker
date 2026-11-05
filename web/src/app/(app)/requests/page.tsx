"use client";

import { useState } from "react";
import { Button, Card, ErrorText, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { FacultyRequest, FacultyRequests } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const STATUS_LABELS: Record<FacultyRequest["status"], string> = {
  pending: "Waiting",
  accepted: "Accepted",
  declined: "Declined",
  cancelled: "Cancelled",
  expired: "Expired",
};

export default function RequestsPage() {
  const { data, error, reload } = useFetch<FacultyRequests>("/faculty-requests");
  const [actError, setActError] = useState<string | null>(null);

  async function act(id: string, action: "accept" | "decline" | "cancel") {
    setActError(null);
    try {
      await api(`/faculty-requests/${id}/${action}`, { method: "POST" });
      await reload();
    } catch (err) {
      setActError(errorText(err));
    }
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!data) return null;
  return (
    <>
      <PageHeader eyebrow="Across departments" title="Requests" />
      <ErrorText>{actError}</ErrorText>
      <h2>Asked of you</h2>
      {data.incoming.length === 0 ? <Card><p className="muted">Nothing waiting for your answer.</p></Card> : (
        <Table label="Requests asked of you" head={["Request", "From", "Answer by", ""]}>
          {data.incoming.map((r) => (
            <tr key={r.id}>
              <td>{r.target}{r.note && <div className="muted">{r.note}</div>}</td>
              <td>{r.requested_by_name}</td>
              <td>{formatDate(r.expires_at.slice(0, 10))}</td>
              <td>
                <Button kind="primary" onClick={() => act(r.id, "accept")}>Accept</Button>{" "}
                <Button kind="ghost" onClick={() => act(r.id, "decline")}>Decline</Button>
              </td>
            </tr>
          ))}
        </Table>
      )}
      <h2 style={{ marginTop: "var(--space-5)" }}>Sent by you</h2>
      {data.sent.length === 0 ? <Card><p className="muted">You have not sent any requests.</p></Card> : (
        <Table label="Requests you sent" head={["Request", "To", "Status", ""]}>
          {data.sent.map((r) => (
            <tr key={r.id}>
              <td>{r.target}</td>
              <td>{r.faculty_name ?? r.email}</td>
              <td><span className="badge">{STATUS_LABELS[r.status]}</span></td>
              <td>
                {r.status === "pending" && (
                  <Button kind="ghost" onClick={() => act(r.id, "cancel")}>Cancel</Button>
                )}
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
