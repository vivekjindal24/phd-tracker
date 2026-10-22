"use client";

import Link from "next/link";
import { Owl } from "@/components/brand/Owl";
import { ErrorText, PageHeader, Table } from "@/components/ui/kit";
import type { QueueEntry } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const STUCK_DAYS = 14; // PRD F10: items stuck longer than this are flagged

export default function QueuePage() {
  const { data, error } = useFetch<QueueEntry[]>("/queue");
  return (
    <>
      <PageHeader eyebrow="Waiting for you" title="Your queue" />
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table
          label="Items waiting for your decision"
          head={["Item", "Scholar", "Your step", "Waiting"]}
          empty={
            <div className="empty-state">
              <Owl pose="cheering" size={96} />
              <h2>All caught up</h2>
              <p>Nothing is waiting for your decision.</p>
            </div>
          }
        >
          {data.map((q) => (
            <tr key={`${q.item_type}-${q.id}`}>
              <td><Link href={`/items/${q.item_type}/${q.id}`}>{q.label} · {q.title}</Link></td>
              <td>{q.scholar.name}</td>
              <td>{q.step}</td>
              <td>
                <span className={`badge ${q.days_waiting > STUCK_DAYS ? "badge-sent_back" : ""}`}>
                  {q.days_waiting === 0 ? "Today" : `${q.days_waiting} day${q.days_waiting === 1 ? "" : "s"}`}
                </span>
              </td>
            </tr>
          ))}
        </Table>
      )}
    </>
  );
}
