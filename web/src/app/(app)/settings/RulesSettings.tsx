"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, Field, Switch } from "@/components/ui/kit";
import type { SettingsData } from "@/lib/types";
import type { Save } from "./save";

/** University ordinance values for the UGC rules the system warns about (PRD Phase 4). */
const FIELDS = [
  ["min_coursework_credits", "Minimum coursework credits", "UGC: 12", 0, 40, 0.5],
  ["min_coursework_cgpa", "Minimum coursework CGPA (out of 10)", "UGC: 55% ≈ 5.5", 0, 10, 0.01],
  ["max_duration_years", "Maximum duration (years from admission)", "UGC: 6", 3, 12, 1],
  ["max_extension_days", "Extension allowed (days)", "UGC: 2 years = 730", 0, 1825, 1],
  ["max_relaxation_days", "Relaxation for women / PwD (days)", "UGC: 2 years = 730", 0, 1825, 1],
  ["max_maternity_leave_days", "Maternity / child-care leave (days)", "UGC: 240, once", 0, 1825, 1],
] as const;
type Key = (typeof FIELDS)[number][0];

const fromSettings = (data: SettingsData) =>
  Object.fromEntries(FIELDS.map(([k]) => [k, String(data[k])])) as Record<Key, string>;

export function RulesSettings({ data, save }: { data: SettingsData; save: Save }) {
  const [values, setValues] = useState(() => fromSettings(data));
  useEffect(() => setValues(fromSettings(data)), [data]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const body = Object.fromEntries(FIELDS.map(([k]) => [k, Number(values[k])]));
    save("/settings", "PATCH", body).catch(() => {}); // the page shows errors
  }

  return (
    <Card>
      <h2>UGC rules</h2>
      <p className="muted">UGC 2022 sets the floor; your ordinance may be stricter. Records are checked against these values and warned about before a rule is broken.</p>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          {FIELDS.map(([key, label, hint, min, max, step]) => (
            <Field key={key} label={label} hint={hint}>
              <input type="number" min={min} max={max} step={step} required value={values[key]}
                onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))} />
            </Field>
          ))}
        </div>
        <Button kind="secondary" type="submit">Save rules</Button>
      </form>
      <ul className="module-list">
        <li>
          <span>A thesis needs an approved no-dues clearance (lab, department, library, fees)</span>
          <Switch checked={data.require_no_dues} label="Thesis needs no-dues clearance"
            onChange={(v) => save("/settings", "PATCH", { require_no_dues: v }).catch(() => {})} />
        </li>
      </ul>
    </Card>
  );
}
