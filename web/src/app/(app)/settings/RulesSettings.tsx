"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, Field, Switch } from "@/components/ui/kit";
import { PATENT_VERIFIER_LABELS } from "@/lib/types";
import type { PatentVerifier, SettingsData } from "@/lib/types";
import type { Save } from "./save";

/** University ordinance values for the UGC rules the system warns about (PRD Phase 4). */
const FIELDS = [
  ["min_coursework_credits", "Minimum coursework credits", "UGC: 12", 0, 40, 0.5],
  ["min_coursework_cgpa", "Minimum coursework CGPA (out of 10)", "UGC: 55% ≈ 5.5", 0, 10, 0.01],
  ["max_duration_years", "Maximum duration (years from admission)", "UGC: 6", 3, 12, 1],
  ["max_extension_days", "Extension allowed (days)", "UGC: 2 years = 730", 0, 1825, 1],
  ["max_relaxation_days", "Relaxation for women / PwD (days)", "UGC: 2 years = 730", 0, 1825, 1],
  ["max_maternity_leave_days", "Maternity / child-care leave (days)", "UGC: 240, once", 0, 1825, 1],
  ["min_duration_years", "Thesis not before (years from admission)", "UGC: 3 · 0 = no minimum", 0, 6, 1],
  ["max_plagiarism_percent", "Plagiarism limit for the thesis (%)", "UGC Level 0: 10", 0, 100, 0.01],
  ["min_publications", "Approved publications before the thesis", "UGC 2022: none · 0 = off", 0, 10, 1],
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
      <p className="muted">UGC 2022 sets the floor; your ordinance may be stricter. Records are checked against these values and warned about before a rule is broken; a thesis is not submitted, nor passed by the Library, until it meets the thesis limits.</p>
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
        <li>
          <span>A thesis needs an ethics record: a committee clearance, or a recorded &ldquo;not required&rdquo;</span>
          <Switch checked={data.require_ethics} label="Thesis needs an ethics record"
            onChange={(v) => save("/settings", "PATCH", { require_ethics: v }).catch(() => {})} />
        </li>
        <li>
          <span>Only publications indexed in Scopus, Web of Science or UGC-CARE count towards the thesis</span>
          <Switch checked={data.publications_indexed_only} label="Only indexed publications count"
            onChange={(v) => save("/settings", "PATCH", { publications_indexed_only: v }).catch(() => {})} />
        </li>
        <li>
          <span>The paper itself must be attached to every publication: a scholar cannot submit one without it, and the Library cannot verify a faculty paper without it. Off: attaching it is optional.</span>
          <Switch checked={data.publication_file_required} label="Require the paper file"
            onChange={(v) => save("/settings", "PATCH", { publication_file_required: v }).catch(() => {})} />
        </li>
        <li>
          <span>Who checks patents against the patent office&apos;s record, and verifies or returns them. Only verified patents count in the NAAC data.</span>
          <select aria-label="Who verifies patents" value={data.patent_verifier}
            onChange={(e) => save("/settings", "PATCH", { patent_verifier: e.target.value }).catch(() => {})}>
            {(Object.keys(PATENT_VERIFIER_LABELS) as PatentVerifier[]).map((k) => (
              <option key={k} value={k}>The {PATENT_VERIFIER_LABELS[k]}</option>
            ))}
          </select>
        </li>
        <li>
          <span>Everyone who logs in with a password also needs a code from an authenticator app. Switch this on for a live university; each person sets it up at their next log in.</span>
          <Switch checked={data.require_two_factor} label="Require two-factor login"
            onChange={(v) => save("/settings", "PATCH", { require_two_factor: v }).catch(() => {})} />
        </li>
        <li>
          <span>Every approve and send-back is signed: the signer needs their signature on file, confirmed by their department admin or the Research Office, and a fresh code from their authenticator app or by email. Switch this on for a live university once signatures are collected.</span>
          <Switch checked={data.require_signing} label="Require signing approvals"
            onChange={(v) => save("/settings", "PATCH", { require_signing: v }).catch(() => {})} />
        </li>
      </ul>
    </Card>
  );
}
