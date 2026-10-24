"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, Field } from "@/components/ui/kit";
import type { SettingsData } from "@/lib/types";
import type { Save } from "./save";

/** University ordinance values for the UGC rules the system warns about (PRD Phase 4). */
export function RulesSettings({ data, save }: { data: SettingsData; save: Save }) {
  const [credits, setCredits] = useState(String(data.min_coursework_credits));
  const [cgpa, setCgpa] = useState(String(data.min_coursework_cgpa));
  useEffect(() => {
    setCredits(String(data.min_coursework_credits));
    setCgpa(String(data.min_coursework_cgpa));
  }, [data.min_coursework_credits, data.min_coursework_cgpa]);

  function submit(e: FormEvent) {
    e.preventDefault();
    save("/settings", "PATCH", { min_coursework_credits: Number(credits), min_coursework_cgpa: Number(cgpa) })
      .catch(() => {}); // the page shows errors
  }

  return (
    <Card>
      <h2>UGC rules</h2>
      <p className="muted">UGC 2022 sets the floor; your ordinance may be stricter. Records are checked against these values and warned about before a rule is broken.</p>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          <Field label="Minimum coursework credits" hint="UGC: 12">
            <input type="number" min={0} max={40} step={0.5} required value={credits} onChange={(e) => setCredits(e.target.value)} />
          </Field>
          <Field label="Minimum coursework CGPA (out of 10)" hint="UGC: 55% ≈ 5.5">
            <input type="number" min={0} max={10} step={0.01} required value={cgpa} onChange={(e) => setCgpa(e.target.value)} />
          </Field>
        </div>
        <Button kind="secondary" type="submit">Save rules</Button>
      </form>
    </Card>
  );
}
