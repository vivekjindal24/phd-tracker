"use client";

import { useEffect, useState } from "react";
import { Button, Card, Switch } from "@/components/ui/kit";
import type { RubricCriterion, SettingsData } from "@/lib/types";
import type { Save } from "./save";

const MAX_CRITERIA = 10;

export function SeminarSettings({ data, save }: { data: SettingsData; save: Save }) {
  const [rubric, setRubric] = useState<RubricCriterion[]>(data.seminar_rubric);
  useEffect(() => setRubric(data.seminar_rubric), [data.seminar_rubric]);
  const dirty = JSON.stringify(rubric) !== JSON.stringify(data.seminar_rubric);
  const total = rubric.reduce((sum, c) => sum + (Number(c.max) || 0), 0);
  const edit = (i: number, patch: Partial<RubricCriterion>) =>
    setRubric(rubric.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const quiet = (p: Promise<void>) => p.catch(() => {}); // the page shows errors

  return (
    <Card className="settings-seminars">
      <h2>Progress seminars</h2>
      <ul className="module-list">
        <li>
          <span>Require a hardcopy of the report</span>
          <Switch checked={data.require_hardcopy} label="Require a hardcopy of the report"
            onChange={(v) => quiet(save("/settings", "PATCH", { require_hardcopy: v }))} />
        </li>
      </ul>
      <fieldset className="segmented" style={{ marginTop: "var(--space-4)" }}>
        <legend><h3>Who may grade</h3></legend>
        {([["panel", "Named panel only", "Only the faculty the department adds to the seminar."],
           ["panel_and_attending", "Panel + attending faculty", "Any faculty member can mark themselves attending and grade."]] as const)
          .map(([value, label, hint]) => (
            <label key={value} className={data.seminar_graders === value ? "chosen" : undefined}>
              <input type="radio" name="graders" checked={data.seminar_graders === value}
                onChange={() => quiet(save("/settings", "PATCH", { seminar_graders: value }))} />
              <strong>{label}</strong>
              <span>{hint}</span>
            </label>
          ))}
      </fieldset>
      <h3 style={{ marginTop: "var(--space-5)" }}>Marking rubric · total {total}</h3>
      <p className="muted">One criterion = a single score. Each grader scores every criterion.</p>
      <ol className="rubric">
        {rubric.map((c, i) => (
          <li key={i}>
            <input aria-label={`Criterion ${i + 1} name`} value={c.name} maxLength={60}
              onChange={(e) => edit(i, { name: e.target.value })} />
            <span className="muted">out of</span>
            <input aria-label={`Criterion ${i + 1} maximum`} type="number" min={1} max={100} value={c.max}
              onChange={(e) => edit(i, { max: Number(e.target.value) })} />
            <button type="button" aria-label={`Remove ${c.name}`} disabled={rubric.length === 1}
              onClick={() => setRubric(rubric.filter((_, j) => j !== i))}>×</button>
          </li>
        ))}
      </ol>
      <div className="row">
        <Button disabled={rubric.length >= MAX_CRITERIA}
          onClick={() => setRubric([...rubric, { name: "", max: 10 }])}>Add criterion</Button>
        {dirty && (
          <>
            <Button kind="primary" onClick={() => quiet(save("/settings", "PATCH", { seminar_rubric: rubric }))}>Save rubric</Button>
            <Button kind="ghost" onClick={() => setRubric(data.seminar_rubric)}>Undo</Button>
          </>
        )}
      </div>
    </Card>
  );
}
