"use client";

import Link from "next/link";
import { formatDate } from "@/lib/format";
import { useFetch } from "@/lib/useFetch";
import { Card } from "./ui/kit";
import "./timeline.css";

type Event = { at: string; kind: "meeting" | "report" | "decision" | "seminar"; title: string; detail: string | null; link: string; badge: string | null };

const ICON: Record<Event["kind"], string> = { meeting: "💬", report: "📝", decision: "🏛️", seminar: "🎤" };
const BADGE: Record<string, string> = {
  draft: "badge-draft", in_review: "badge-in_review", sent_back: "badge-sent_back", approved: "badge-approved",
  Approved: "badge-approved", Pending: "badge-draft", Rejected: "badge-sent_back", cancelled: "badge-sent_back",
};
const BADGE_TEXT: Record<string, string> = { in_review: "In review", sent_back: "Sent back", draft: "Draft", approved: "Approved" };

/** Everything about a scholar in date order, each row filtered by the viewer's rights. */
export function Timeline({ scholarId }: { scholarId: string }) {
  const { data } = useFetch<Event[]>(`/scholars/${scholarId}/timeline`);
  if (!data) return null;
  return (
    <Card className="timeline-card">
      <h2>Timeline</h2>
      {data.length === 0 ? <p className="muted">Nothing recorded yet.</p> : (
        <ol className="timeline">
          {data.map((e, i) => (
            <li key={`${e.kind}-${e.link}-${i}`}>
              <span className="timeline-icon" aria-hidden="true">{ICON[e.kind]}</span>
              <div>
                <time dateTime={e.at}>{formatDate(e.at.slice(0, 10))}</time>
                <Link href={e.link}>{e.title}</Link>
                {e.badge && <span className={`badge ${BADGE[e.badge] ?? ""}`}>{BADGE_TEXT[e.badge] ?? e.badge}</span>}
                {e.detail && <span className="muted"> · {e.detail}</span>}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
