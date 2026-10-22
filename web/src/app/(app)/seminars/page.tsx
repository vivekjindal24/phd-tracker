"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { formatDate, formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { SeminarRow } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./seminars.css";

export default function SeminarsPage() {
  const { me } = useSession();
  const [upcoming, setUpcoming] = useState(true);
  const { data, error } = useFetch<SeminarRow[]>(`/seminars?upcoming=${upcoming}`);
  const canSchedule = me?.roles.some((r) => r === "unit_head" || r === "admin") ?? false;

  return (
    <>
      <PageHeader
        eyebrow="Six-monthly review"
        title="Progress seminars"
        actions={
          <div className="row">
            <button type="button" className={`btn ${upcoming ? "btn-secondary" : ""}`} onClick={() => setUpcoming(true)}>Upcoming</button>
            <button type="button" className={`btn ${!upcoming ? "btn-secondary" : ""}`} onClick={() => setUpcoming(false)}>All</button>
            {canSchedule && <Link href="/seminars/new" className="btn btn-primary">Schedule seminar</Link>}
          </div>
        }
      />
      <ErrorText>{error}</ErrorText>
      {data && data.length === 0 && (
        <Card className="empty-state">
          <Owl pose="empty" size={96} />
          <h2>{upcoming ? "No upcoming seminars" : "No seminars yet"}</h2>
          <p>{canSchedule ? "Schedule one for your department." : "You'll be notified when your department schedules one."}</p>
        </Card>
      )}
      <div className="seminar-cards">
        {data?.map((s) => (
          <Link key={s.id} href={`/seminars/${s.id}`}
            className={`clay card seminar-card${s.status === "cancelled" ? " seminar-cancelled" : ""}`}>
            <span className="seminar-when">{formatWhen(s.starts_at)}</span>
            <h2>{s.title}</h2>
            <span className="muted">{s.unit.name} · {s.venue || "Venue to be announced"}</span>
            <span>
              <span className="badge">{s.scholar_count} scholar{s.scholar_count === 1 ? "" : "s"}</span>{" "}
              <span className="badge badge-draft">Report due {formatDate(s.report_due)}</span>{" "}
              {s.status === "cancelled" && <span className="badge badge-sent_back">Cancelled</span>}
            </span>
          </Link>
        ))}
      </div>
    </>
  );
}
