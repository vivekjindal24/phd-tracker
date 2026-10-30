"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment, useEffect, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { Celebrate, firstTime } from "@/components/Celebrate";
import { Button, Card, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
import { useSession } from "@/lib/session";
import { PART_LABELS } from "@/lib/types";
import type { Point, ReviewView, TodoPart } from "@/lib/types";
import { errorText } from "@/lib/useFetch";
import "../../../seminars.css";
import "./review.css";

const PARTS = Object.keys(PART_LABELS) as TodoPart[];

function GradeForm({ review, onSaved }: { review: ReviewView; onSaved: (r: ReviewView) => void }) {
  const initial = Object.fromEntries(review.rubric.map((c) => [c.name, review.my_grade?.scores[c.name] ?? ""]));
  const [scores, setScores] = useState<Record<string, number | string>>(initial);
  const [comment, setComment] = useState(review.my_grade?.comment ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function submit() {
    setError(null);
    setSaved(false);
    try {
      onSaved(await api<ReviewView>(`/seminars/${review.seminar_id}/scholars/${review.scholar.id}/grade`, {
        method: "PUT",
        body: JSON.stringify({ scores: Object.fromEntries(Object.entries(scores).map(([k, v]) => [k, Number(v)])), comment }),
      }));
      setSaved(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <Card className="grade-form">
      <h2>{review.my_grade ? "Your marks (you can still change them)" : "Your marks"}</h2>
      <div className="rubric-inputs">
        {review.rubric.map((c) => (
          <Field key={c.name} label={`${c.name} (out of ${c.max})`}>
            <input type="number" min={0} max={c.max} step={0.5} required value={scores[c.name] ?? ""}
              onChange={(e) => setScores({ ...scores, [c.name]: e.target.value })} />
          </Field>
        ))}
      </div>
      <Field label="Comments for the scholar" hint="Concrete suggestions work best — the supervisor turns them into to-do points.">
        <textarea value={comment} maxLength={8000} onChange={(e) => setComment(e.target.value)} />
      </Field>
      <ErrorText>{error}</ErrorText>
      {saved && <p className="muted" role="status">Marks saved.</p>}
      <Button kind="primary" onClick={submit}>{review.my_grade ? "Update marks" : "Submit marks"}</Button>
    </Card>
  );
}

function PointsEditor({ review, onSaved }: { review: ReviewView; onSaved: (r: ReviewView) => void }) {
  const [points, setPoints] = useState<Point[]>(review.draft_points);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"ai" | "save" | "final" | null>(null);
  useEffect(() => setPoints(review.draft_points), [review.draft_points]);
  const base = `/seminars/${review.seminar_id}/scholars/${review.scholar.id}`;

  async function run(kind: "ai" | "save" | "final") {
    setBusy(kind);
    setError(null);
    try {
      const path = kind === "ai" ? "suggest" : kind === "save" ? "draft" : "finalise";
      const method = kind === "save" ? "PUT" : "POST";
      const body = kind === "ai" ? undefined : JSON.stringify({ points: points.filter((p) => p.text.trim()) });
      onSaved(await api<ReviewView>(`${base}/${path}`, { method, body }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card className="points-editor">
      <h2>To-do points for the scholar</h2>
      <p className="muted">
        {review.ai_available
          ? "Let AI draft points from the panel's comments, then edit, remove or add your own."
          : "Write the points the scholar should work on, each tagged with the part it concerns."}
      </p>
      {review.ai_available && (
        <Button kind="secondary" disabled={busy !== null || review.grades.length === 0} onClick={() => run("ai")}>
          {busy === "ai" ? "Drafting…" : "✨ Suggest points with AI"}
        </Button>
      )}
      <ol className="points">
        {points.map((p, i) => (
          <li key={i}>
            <select aria-label={`Part for point ${i + 1}`} value={p.part}
              onChange={(e) => setPoints(points.map((q, j) => (j === i ? { ...q, part: e.target.value as TodoPart } : q)))}>
              {PARTS.map((k) => <option key={k} value={k}>{PART_LABELS[k]}</option>)}
            </select>
            <input aria-label={`Point ${i + 1}`} value={p.text} maxLength={1000}
              onChange={(e) => setPoints(points.map((q, j) => (j === i ? { ...q, text: e.target.value } : q)))} />
            <button type="button" aria-label={`Remove point ${i + 1}`}
              onClick={() => setPoints(points.filter((_, j) => j !== i))}>×</button>
          </li>
        ))}
      </ol>
      <div className="row">
        <Button onClick={() => setPoints([...points, { part: "other", text: "" }])}>Add point</Button>
        <Button kind="ghost" disabled={busy !== null} onClick={() => run("save")}>Save draft</Button>
      </div>
      <ErrorText>{error}</ErrorText>
      <div className="finalise">
        <p className="muted">Finalising releases every grader&apos;s marks and comments to the scholar and adds these points to their to-do list. Grades lock.</p>
        <Button kind="primary" disabled={busy !== null || review.grades.length === 0}
          onClick={() => { if (window.confirm("Finalise and release the feedback to the scholar?")) run("final"); }}>
          {busy === "final" ? "Finalising…" : "Finalise & release"}
        </Button>
      </div>
    </Card>
  );
}

export default function ReviewPage() {
  const { id, scholarId } = useParams<{ id: string; scholarId: string }>();
  const [review, setReview] = useState<ReviewView | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [celebrate, setCelebrate] = useState(false);
  const { me } = useSession();

  useEffect(() => {
    api<ReviewView>(`/seminars/${id}/scholars/${scholarId}/review`)
      .then(setReview)
      .catch((e) => setError(e instanceof ApiError ? e : new ApiError(0, "unknown", String(e))));
  }, [id, scholarId]);

  // The scholar celebrates once, the first time they open their finalised feedback.
  const isOwnFinalised = !!review?.finalised_at && review.scholar.id === me?.scholar_id;
  useEffect(() => {
    if (isOwnFinalised && firstTime(`seminar.${id}.${scholarId}`)) setCelebrate(true);
  }, [isOwnFinalised, id, scholarId]);

  if (error?.status === 403) {
    return (
      <Card className="empty-state">
        <Owl pose="reading" size={110} />
        <h2>Feedback isn&apos;t released yet</h2>
        <p>Your marks, the panel&apos;s comments and your to-do points appear here once your supervisor finalises the review.</p>
        <Link href={`/seminars/${id}`}>← Back to the seminar</Link>
      </Card>
    );
  }
  if (error) return <ErrorText>{error.message}</ErrorText>;
  if (!review) return null;
  return (
    <>
      {celebrate && <Celebrate message="Feedback is in! 🦉" onDone={() => setCelebrate(false)} />}
      <PageHeader eyebrow={review.seminar_title} title={`Seminar feedback · ${review.scholar.name}`}
        actions={review.finalised_at ? <span className="badge badge-approved">Finalised</span> : undefined} />
      <div className="review-grid">
        <div className="review-main">
          {review.can_grade && <GradeForm review={review} onSaved={setReview} />}
          <Card>
            <h2>Marks{review.average_percent !== null && ` · average ${review.average_percent}%`}</h2>
            {review.grades.length === 0 ? <p className="muted">No marks submitted yet.</p> : (
              <div className="grade-cards">
                {review.grades.map((g) => (
                  <article key={g.grader} className="grade-card">
                    <header><strong>{g.grader}</strong><span className="badge">{g.total} / {g.max_total}</span></header>
                    <dl className="kv">
                      {g.rubric.map((c) => (
                        <Fragment key={c.name}><dt>{c.name}</dt><dd>{g.scores[c.name]} / {c.max}</dd></Fragment>
                      ))}
                    </dl>
                    {g.comment && <blockquote>{g.comment}</blockquote>}
                  </article>
                ))}
              </div>
            )}
          </Card>
        </div>
        <div className="review-side">
          {review.can_finalise && <PointsEditor review={review} onSaved={setReview} />}
          {review.finalised_at && (
            <Card>
              <h2>To-do points</h2>
              {review.todos.length === 0 ? <p className="muted">No changes requested.</p> : (
                <ul className="todo-list">
                  {review.todos.map((t) => (
                    <li key={t.id} className={t.status === "done" ? "done" : undefined}>
                      <span className="badge">{PART_LABELS[t.part]}</span> {t.text}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}
          <p><Link href={`/seminars/${review.seminar_id}`}>← Back to the seminar</Link></p>
        </div>
      </div>
    </>
  );
}
