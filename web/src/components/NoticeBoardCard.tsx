"use client";

import Link from "next/link";
import { Card } from "@/components/ui/kit";
import { formatDay } from "@/lib/format";
import type { Notice } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** Home: the latest notices from the notice board, pinned first. */
export function NoticeBoardCard() {
  const { data } = useFetch<Notice[]>("/announcements");
  if (!data || data.length === 0) return null;
  return (
    <Card className="notice-board-card">
      <h3>Notices</h3>
      <ul className="plain-list">
        {data.slice(0, 3).map((n) => (
          <li key={n.id}>
            {n.pinned && <span className="badge">Pinned</span>} <strong>{n.title}</strong>
            <span className="muted"> · {n.unit?.name ?? "Whole university"} · {formatDay(n.posted_at)}</span>
          </li>
        ))}
      </ul>
      <Link href="/notices">All notices →</Link>
    </Card>
  );
}
