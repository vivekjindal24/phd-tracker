"use client";

import { useEffect, useState } from "react";
import { Button, Card, Field } from "@/components/ui/kit";
import { SEMINAR_KIND_LABELS } from "@/lib/types";
import type { SeminarForm, SeminarKind, SettingsData } from "@/lib/types";
import type { Save } from "./save";

const MAX_QUESTIONS = 20;
const KINDS = Object.keys(SEMINAR_KIND_LABELS) as SeminarKind[];

/** One kind of seminar: marked by the rubric above, or by the university's own form questions. */
function KindForm({ kind, saved, save }: { kind: SeminarKind; saved: SeminarForm; save: Save }) {
  const [form, setForm] = useState<SeminarForm>(saved);
  useEffect(() => setForm(saved), [saved]);
  const dirty = JSON.stringify(form) !== JSON.stringify(saved);
  const questions = form.questions.length ? form.questions : [""];
  const setQuestion = (i: number, text: string) =>
    setForm({ ...form, questions: questions.map((q, j) => (j === i ? text : q)) });
  const clean = { ...form, questions: form.questions.map((q) => q.trim()).filter(Boolean) };

  return (
    <section className="seminar-marking">
      <h3>{SEMINAR_KIND_LABELS[kind]}</h3>
      <fieldset className="segmented">
        <legend className="visually-hidden">How a {SEMINAR_KIND_LABELS[kind].toLowerCase()} is marked</legend>
        {([["rubric", "Rubric scores", "Each grader scores the rubric above."],
           ["questions", "Form questions", "Each grader answers your form's questions and recommends."]] as const)
          .map(([value, label, hint]) => (
            <label key={value} className={form.marking === value ? "chosen" : undefined}>
              <input type="radio" name={`marking-${kind}`} checked={form.marking === value}
                onChange={() => setForm({ ...form, marking: value })} />
              <strong>{label}</strong>
              <span>{hint}</span>
            </label>
          ))}
      </fieldset>
      <Field label="Name of the form here" hint="As the university calls it, e.g. “Form VII”. Printed on the report.">
        <input maxLength={100} value={form.form_name} onChange={(e) => setForm({ ...form, form_name: e.target.value })} />
      </Field>
      {form.marking === "questions" && (
        <>
          <ol className="rubric form-questions">
            {questions.map((q, i) => (
              <li key={i}>
                <input aria-label={`Question ${i + 1}`} value={q} maxLength={300}
                  onChange={(e) => setQuestion(i, e.target.value)} />
                <button type="button" aria-label={`Remove question ${i + 1}`} disabled={questions.length === 1}
                  onClick={() => setForm({ ...form, questions: questions.filter((_, j) => j !== i) })}>×</button>
              </li>
            ))}
          </ol>
          <p className="muted">Each is answered yes or no, with a remark; the panel then recommends.</p>
        </>
      )}
      <div className="row">
        {form.marking === "questions" && (
          <Button disabled={questions.length >= MAX_QUESTIONS}
            onClick={() => setForm({ ...form, questions: [...questions, ""] })}>Add question</Button>
        )}
        {dirty && (
          <>
            <Button kind="primary" onClick={() => save("/settings", "PATCH", { seminar_forms: { [kind]: clean } }).catch(() => {})}>
              Save
            </Button>
            <Button kind="ghost" onClick={() => setForm(saved)}>Undo</Button>
          </>
        )}
      </div>
    </section>
  );
}

/** PRD F15: per kind of seminar, rubric scores or the university's own form (Form VII, VIII …). */
export function SeminarForms({ data, save }: { data: SettingsData; save: Save }) {
  return (
    <Card className="settings-seminar-forms">
      <h2>How each seminar is marked</h2>
      <p className="muted">Universities differ: choose rubric scores or your own form for each kind of seminar.</p>
      {KINDS.map((kind) => <KindForm key={kind} kind={kind} saved={data.seminar_forms[kind]} save={save} />)}
    </Card>
  );
}
