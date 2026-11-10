"use client";

import { useEffect, useState } from "react";
import { Button, Card, Switch } from "@/components/ui/kit";
import type { AprSection, SettingsData } from "@/lib/types";
import type { Save } from "./save";

const MAX_SECTIONS = 10;

/** The sections of the six-monthly progress report: the standard ones, or the university's own. */
export function ReportTemplate({ data, save }: { data: SettingsData; save: Save }) {
  const [sections, setSections] = useState<AprSection[]>(data.apr_sections);
  useEffect(() => setSections(data.apr_sections), [data.apr_sections]);
  const dirty = JSON.stringify(sections) !== JSON.stringify(data.apr_sections);
  const edit = (i: number, patch: Partial<AprSection>) =>
    setSections(sections.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const quiet = (p: Promise<void>) => p.catch(() => {}); // the page shows errors

  return (
    <Card className="settings-seminars">
      <h2>Progress report template</h2>
      <ul className="module-list">
        <li>
          <span>Use our own sections instead of the standard ones</span>
          <Switch checked={data.apr_custom_template} label="Use our own report template"
            onChange={(v) => quiet(save("/settings", "PATCH", { apr_custom_template: v }))} />
        </li>
      </ul>
      {data.apr_custom_template ? (
        <>
          <p className="muted">Scholars write one answer per section. Changes apply to reports not yet submitted.</p>
          <ol className="rubric">
            {sections.map((s, i) => (
              <li key={i}>
                <input aria-label={`Section ${i + 1} heading`} placeholder="Heading" value={s.name} maxLength={200}
                  onChange={(e) => edit(i, { name: e.target.value })} />
                <input aria-label={`Section ${i + 1} hint`} placeholder="Hint for the scholar (optional)" value={s.hint} maxLength={300}
                  style={{ flex: 2 }} onChange={(e) => edit(i, { hint: e.target.value })} />
                <button type="button" aria-label={`Remove ${s.name}`} disabled={sections.length === 1}
                  onClick={() => setSections(sections.filter((_, j) => j !== i))}>×</button>
              </li>
            ))}
          </ol>
          <div className="row">
            <Button disabled={sections.length >= MAX_SECTIONS}
              onClick={() => setSections([...sections, { name: "", hint: "" }])}>Add section</Button>
            {dirty && (
              <>
                <Button kind="primary" onClick={() => quiet(save("/settings", "PATCH", { apr_sections: sections }))}>Save template</Button>
                <Button kind="ghost" onClick={() => setSections(data.apr_sections)}>Undo</Button>
              </>
            )}
          </div>
        </>
      ) : (
        <p className="muted">Standard sections in use: {data.apr_template.map((s) => s.name).join(" · ")}.</p>
      )}
    </Card>
  );
}
