"use client";

import { Field } from "@/components/ui/kit";
import type { AprSection, SectionText } from "@/lib/types";

/** One text area per section of the report template; shared by the new-report form and the edit view. */
export function ReportSections({ template, value, onChange }: {
  template: AprSection[];
  value: SectionText[];
  onChange: (next: SectionText[]) => void;
}) {
  const text = (name: string) => value.find((s) => s.name === name)?.text ?? "";
  const set = (name: string, t: string) =>
    onChange(template.map((s) => ({ name: s.name, text: s.name === name ? t : text(s.name) })));
  return (
    <>
      {template.map((s) => (
        <Field key={s.name} label={s.name} hint={s.hint || undefined}>
          <textarea className="summary-edit" maxLength={20000} value={text(s.name)}
            onChange={(e) => set(s.name, e.target.value)} />
        </Field>
      ))}
    </>
  );
}
