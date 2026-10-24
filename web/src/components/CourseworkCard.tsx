"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { StateBadge } from "@/components/items/StateBadge";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { Course, CourseworkView, ItemView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function Meter({ label, value, min, max }: { label: string; value: number; min: number; max: number }) {
  const ok = value >= min;
  return (
    <div className="meter" aria-label={`${label}: ${value} of minimum ${min}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{label}</strong>
        <span className={ok ? "" : "error-text"}>{value.toFixed(label === "CGPA" ? 2 : 1)} / {min} minimum</span>
      </div>
      <div className="meter-track">
        <div className="meter-fill" style={{ width: `${Math.min(100, (value / max) * 100)}%`, background: ok ? "var(--sage)" : "var(--coral)" }} />
      </div>
    </div>
  );
}

function Enrol({ scholarId, onSaved }: { scholarId: string; onSaved: (v: CourseworkView) => void }) {
  const { data: courses } = useFetch<Course[]>("/courses");
  const [courseId, setCourseId] = useState("");
  const [semester, setSemester] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      onSaved(await api<CourseworkView>("/enrolments", {
        method: "POST",
        body: JSON.stringify({ scholar_id: scholarId, course_id: courseId, semester }),
      }));
      setCourseId("");
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>Enrol in a course</h3>
      <div className="row">
        <Field label="Course">
          <select required value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="" disabled>Choose…</option>
            {courses?.map((c) => <option key={c.id} value={c.id}>{c.code} · {c.title} ({c.credits} cr) · {c.unit.name}</option>)}
          </select>
        </Field>
        <Field label="Semester"><input required maxLength={40} placeholder="2025-26 Odd" value={semester} onChange={(e) => setSemester(e.target.value)} /></Field>
      </div>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit">Enrol</Button>
    </form>
  );
}

function GradeCell({ enrolmentId, grade, points, editable, onSaved }: {
  enrolmentId: string; grade: string | null; points: number | null; editable: boolean; onSaved: (v: CourseworkView) => void;
}) {
  const [g, setG] = useState(grade ?? "");
  const [p, setP] = useState(points === null ? "" : String(points));
  const [error, setError] = useState<string | null>(null);
  if (!editable) return <>{grade ?? "—"}{points !== null && <span className="muted"> ({points})</span>}</>;

  async function save() {
    setError(null);
    try {
      onSaved(await api<CourseworkView>(`/enrolments/${enrolmentId}`, {
        method: "PATCH",
        body: JSON.stringify({ grade: g || null, grade_points: p === "" ? null : Number(p) }),
      }));
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="row">
      <input aria-label="Grade" maxLength={5} size={4} value={g} onChange={(e) => setG(e.target.value)} />
      <input aria-label="Grade points" type="number" min={0} max={10} step={0.01} style={{ width: 80 }} value={p} onChange={(e) => setP(e.target.value)} />
      <Button kind="ghost" onClick={save}>Save</Button>
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** A scholar's coursework against the UGC rules: shows what blocks clearance before anyone
 *  tries (PRD Phase 4). The API enforces the same rules at submit. */
export function CourseworkCard({ scholarId }: { scholarId: string }) {
  const { data: v, error, setData } = useFetch<CourseworkView>(`/scholars/${scholarId}/coursework`);
  const [actError, setActError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;
  const editable = v.can_manage && !v.locked;

  async function startClearance() {
    setActError(null);
    try {
      const item = await api<ItemView>("/clearances", { method: "POST", body: JSON.stringify({ scholar_id: scholarId }) });
      window.location.assign(`/items/coursework_clearance/${item.id}`);
    } catch (e) {
      setActError(errorText(e));
    }
  }

  return (
    <Card className="coursework">
      <h2>Coursework</h2>
      <Meter label="Credits" value={v.credits} min={v.min_credits} max={Math.max(v.min_credits, v.credits, 1)} />
      {v.cgpa !== null && <Meter label="CGPA" value={v.cgpa} min={v.min_cgpa} max={10} />}
      {v.problems.length > 0 && !v.clearance?.cleared_on && (
        <ul className="warn-list" aria-label="Before clearance">
          {v.problems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}
      {v.enrolments.length === 0 ? <p className="muted">No courses yet.</p> : (
        <table className="mini-table">
          <thead><tr><th scope="col">Course</th><th scope="col">Semester</th><th scope="col">Credits</th><th scope="col">Grade</th></tr></thead>
          <tbody>
            {v.enrolments.map((e) => (
              <tr key={e.id}>
                <td>{e.course.code} · {e.course.title}</td>
                <td>{e.semester}</td>
                <td className="mono">{e.course.credits}</td>
                <td><GradeCell enrolmentId={e.id} grade={e.grade} points={e.grade_points} editable={editable} onSaved={setData} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {v.clearance ? (
        <p>Clearance: <Link href={`/items/coursework_clearance/${v.clearance.id}`}>open</Link>{" "}
          <StateBadge state={v.clearance.state} waitingOn={v.clearance.waiting_on} /></p>
      ) : v.can_manage && (
        <Button kind="primary" disabled={v.problems.length > 0} onClick={startClearance}
          title={v.problems.length ? "Fix the items above first" : undefined}>Start coursework clearance</Button>
      )}
      {editable && <Enrol scholarId={scholarId} onSaved={setData} />}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
