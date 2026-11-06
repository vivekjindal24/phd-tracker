"use client";

import Link from "next/link";
import { Card, ErrorText } from "@/components/ui/kit";
import { formatDate } from "@/lib/format";
import { REVIEW_STATUS_LABELS } from "@/lib/types";
import type { ReviewSummary } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export default function ReviewsPage() {
  const { data, error } = useFetch<ReviewSummary[]>("/reviewer/reviews");
  return (
    <>
      <h1>Your thesis reviews</h1>
      <ErrorText>{error}</ErrorText>
      {data?.length === 0 && <p className="muted">You have no reviews yet.</p>}
      <div className="review-side">
        {data?.map((r) => (
          <Card key={r.id}>
            <h2>{r.is_open ? <Link href={`/review/${r.id}`}>{r.thesis_title}</Link> : r.thesis_title}</h2>
            <p className="muted">Due {formatDate(r.deadline)} · {r.is_open ? "Open" : REVIEW_STATUS_LABELS[r.status] === "Accepted" ? "Closed" : REVIEW_STATUS_LABELS[r.status]}</p>
          </Card>
        ))}
      </div>
    </>
  );
}
