"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { ListFoot } from "@/components/ListFoot";
import { formatDate, formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import type { SeminarRow } from "@/lib/types";
import { usePagedFetch } from "@/lib/useFetch";
import { listPath } from "@/components/ScholarFilter";
import "./seminars.css";

export default function SeminarsPage() {
  const { me } = useSession();
  const [upcoming, setUpcoming] = useState(true);
  const [sort, setSort] = useState(""); // cards, not a table: a select stands in for column headers
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<SeminarRow>(
    listPath("/seminars", { upcoming: String(upcoming), sort }), 100);
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
      <div className="toolbar">
        <Field label="Sort by">
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="">{upcoming ? "Soonest first" : "Latest first"}</option>
            <option value="title">Title</option>
            <option value="department">Department</option>
          </select>
        </Field>
      </div>
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
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}
