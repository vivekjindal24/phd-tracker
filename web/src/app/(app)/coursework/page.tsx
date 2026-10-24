"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { CourseworkCard } from "@/components/CourseworkCard";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Course, OrgUnit, Scholar } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function AddCourse({ units, onAdded }: { units: OrgUnit[]; onAdded: () => void }) {
  const [unitId, setUnitId] = useState("");
  const [code, setCode] = useState("");
  const [title, setTitle] = useState("");
  const [credits, setCredits] = useState("4");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/courses", { method: "POST", body: JSON.stringify({ unit_id: unitId, code, title, credits: Number(credits) }) });
      setCode(""); setTitle("");
      onAdded();
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <form className="verify" onSubmit={submit}>
      <h3>Add a course</h3>
      <div className="row">
        <Field label="Unit">
          <select required value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            <option value="" disabled>Choose…</option>
            {units.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
          </select>
        </Field>
        <Field label="Code"><input required maxLength={20} value={code} onChange={(e) => setCode(e.target.value)} /></Field>
        <Field label="Credits"><input type="number" required min={0.5} max={20} step={0.5} value={credits} onChange={(e) => setCredits(e.target.value)} /></Field>
      </div>
      <Field label="Title"><input required maxLength={500} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      <ErrorText>{error}</ErrorText>
      <Button kind="secondary" type="submit">Add course</Button>
    </form>
  );
}

function ScholarPicker({ onPick }: { onPick: (id: string) => void }) {
  const [q, setQ] = useState("");
  const { data } = useFetch<Scholar[]>(q.length >= 2 ? `/scholars?q=${encodeURIComponent(q)}&limit=10` : null);
  return (
    <Card>
      <h2>Grades for a scholar</h2>
      <Field label="Find a scholar" hint="Name or roll number">
        <input value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      {data && (
        <ul className="plain-list">
          {data.map((s) => (
            <li key={s.id}><Button kind="ghost" onClick={() => onPick(s.id)}>{s.full_name} · {s.roll_number} · {s.unit.name}</Button></li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export default function CourseworkPage() {
  const { me } = useSession();
  const { data: courses, error, reload } = useFetch<Course[]>("/courses");
  const { data: units } = useFetch<OrgUnit[]>("/org-units");
  const [picked, setPicked] = useState<string | null>(null);
  const isExam = me?.office_roles.includes("exam_office") ?? false;
  const adminPaths = me?.unit_roles.filter((r) => r.role === "admin").map((r) => r.unit_path) ?? [];
  const writable = (units ?? []).filter((u) => isExam || adminPaths.some((p) => u.path === p || u.path.startsWith(`${p}.`)));

  return (
    <>
      <PageHeader eyebrow="Academic administration" title="Coursework" />
      {me?.scholar_id && <CourseworkCard scholarId={me.scholar_id} />}
      {isExam && <ScholarPicker onPick={setPicked} />}
      {picked && <div style={{ marginTop: "var(--space-5)" }}><CourseworkCard key={picked} scholarId={picked} /></div>}
      <h2 style={{ marginTop: "var(--space-6)" }}>Course catalogue</h2>
      <ErrorText>{error}</ErrorText>
      {courses && (
        <Table label="Course catalogue" head={["Code", "Title", "Credits", "Unit"]}
          empty={<p className="muted" style={{ padding: "var(--space-5)" }}>No courses yet.</p>}>
          {courses.map((c) => (
            <tr key={c.id}><td className="mono">{c.code}</td><td>{c.title}</td><td className="mono">{c.credits}</td><td>{c.unit.name}</td></tr>
          ))}
        </Table>
      )}
      {writable.length > 0 && <Card><AddCourse units={writable} onAdded={reload} /></Card>}
    </>
  );
}
