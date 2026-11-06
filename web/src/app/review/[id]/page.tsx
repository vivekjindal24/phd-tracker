"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Attachments } from "@/components/Attachments";
import { DownloadButton } from "@/components/DownloadButton";
import { PdfViewer } from "@/components/review/PdfViewer";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { RECOMMENDATION_LABELS } from "@/lib/types";
import type { Recommendation, ReviewDetail, ReviewSummary } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const { data, error, setData, reload } = useFetch<ReviewDetail>(`/reviewer/reviews/${id}`);
  const [page, setPage] = useState(1);
  const [commentPage, setCommentPage] = useState<number | null>(null);
  const [body, setBody] = useState("");
  const [recommendation, setRecommendation] = useState<Recommendation | "">("");
  const [actError, setActError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function act(run: () => Promise<void>) {
    setBusy(true);
    setActError(null);
    try {
      await run();
    } catch (e) {
      setActError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  function addComment(e: FormEvent) {
    e.preventDefault();
    void act(async () => {
      await api(`/reviewer/reviews/${id}/comments`, {
        method: "POST",
        body: JSON.stringify({ page: commentPage ?? page, body }),
      });
      setBody("");
      setCommentPage(null);
      reload();
    });
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    void act(async () => {
      const done = await api<ReviewSummary>(`/reviewer/reviews/${id}/submit`, {
        method: "POST",
        body: JSON.stringify({ recommendation }),
      });
      if (data) setData({ ...data, ...done });
    });
  }

  if (error) return <ErrorText>{error}</ErrorText>;
  if (!data) return null;
  if (!data.is_open) {
    return (
      <Card>
        <h1>{data.thesis_title}</h1>
        <p role="status">
          {data.status === "submitted" ? "Your review has been submitted. Thank you." : "This review is closed. Please contact the Exam Office if you need more time."}
        </p>
        <Link href="/review">Back to your reviews</Link>
      </Card>
    );
  }
  return (
    <>
      <h1>{data.thesis_title}</h1>
      <p className="muted">
        Due {formatDate(data.deadline)}. This copy is uniquely marked and traceable to you. Comments are optional: add as many or as few as you like, or upload your own review.
      </p>
      <div className="review-work">
        <Card>
          <PdfViewer path={`/reviews/${id}/thesis.pdf`} page={page} onPage={setPage} />
          {data.allow_download && <DownloadButton path={`/reviews/${id}/thesis.pdf?download=1`}>Download thesis</DownloadButton>}
        </Card>
        <div className="review-side">
          <Card>
            <h2>Your comments</h2>
            {data.comments.length === 0 ? <p className="muted">None yet.</p> : (
              <ul className="plain-list">
                {data.comments.map((c) => (
                  <li key={c.id} className="review-comment">
                    <span><strong>Page {c.page}:</strong> {c.body}</span>
                    <Button kind="ghost" aria-label={`Remove comment on page ${c.page}`} disabled={busy} onClick={() => act(async () => {
                      await api(`/reviewer/comments/${c.id}`, { method: "DELETE" });
                      reload();
                    })}>Remove</Button>
                  </li>
                ))}
              </ul>
            )}
            <form onSubmit={addComment}>
              <Field label="Page"><input type="number" required min={1} value={commentPage ?? page} onChange={(e) => setCommentPage(Number(e.target.value))} /></Field>
              <Field label="Comment"><textarea required rows={3} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} /></Field>
              <Button kind="secondary" type="submit" disabled={busy}>Add comment</Button>
            </form>
          </Card>
          <Card>
            <Attachments table="thesis_reviews" recordId={id} canUpload title="Your review file" />
          </Card>
          <Card>
            <h2>Submit your review</h2>
            <form onSubmit={submit}>
              <Field label="Recommendation">
                <select required value={recommendation} onChange={(e) => setRecommendation(e.target.value as Recommendation)}>
                  <option value="">Choose…</option>
                  {(Object.keys(RECOMMENDATION_LABELS) as Recommendation[]).map((r) => <option key={r} value={r}>{RECOMMENDATION_LABELS[r]}</option>)}
                </select>
              </Field>
              <p className="muted">Once submitted, your review is locked and your access to the thesis ends.</p>
              <ErrorText>{actError}</ErrorText>
              <Button kind="primary" type="submit" disabled={busy}>Submit review</Button>
            </form>
          </Card>
        </div>
      </div>
    </>
  );
}
