"use client";

import { useEffect, useState } from "react";
import { Button, Card, Field } from "@/components/ui/kit";
import type { PhdFormName, SettingsData } from "@/lib/types";
import type { Save } from "./save";

type Draft = { title: string; number: string; copyTo: string };
const draftOf = (n: PhdFormName | undefined): Draft =>
  ({ title: n?.title ?? "", number: n?.number ?? "", copyTo: (n?.copy_to ?? []).join("\n") });

/** One form of the PhD file: the university's title, form number and "copy to" list. */
function OneForm({ formKey, standard, saved, save }: {
  formKey: string; standard: string; saved: PhdFormName | undefined; save: Save;
}) {
  const [draft, setDraft] = useState<Draft>(draftOf(saved));
  useEffect(() => setDraft(draftOf(saved)), [saved]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(draftOf(saved));
  const notice = formKey.endsWith("_notice");
  const body = {
    title: draft.title.trim(),
    number: draft.number.trim(),
    copy_to: draft.copyTo.split("\n").map((l) => l.trim()).filter(Boolean),
  };
  const shown = [saved?.number, saved?.title || standard].filter(Boolean).join(" — ");

  return (
    <details className="phd-form">
      <summary>{shown}</summary>
      <div className="stack-form">
        <div className="row">
          <Field label="Form number" hint="As on your paper, e.g. “Form VII-A”. Printed at the top right.">
            <input maxLength={30} value={draft.number} onChange={(e) => setDraft({ ...draft, number: e.target.value })} />
          </Field>
          <Field label="Title">
            <input maxLength={120} placeholder={standard} value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })} />
          </Field>
        </div>
        <Field label="Copy to" hint={notice
          ? "One per line. Left empty, Anveshan's list is used; a department admin may still change it for one seminar or viva."
          : "One per line. Left empty, the form keeps its own list (most have none)."}>
          <textarea rows={3} value={draft.copyTo} onChange={(e) => setDraft({ ...draft, copyTo: e.target.value })} />
        </Field>
        {dirty && (
          <div className="row">
            <Button kind="primary" onClick={() => save("/settings", "PATCH", { phd_forms: { [formKey]: body } }).catch(() => {})}>
              Save
            </Button>
            <Button kind="ghost" onClick={() => setDraft(draftOf(saved))}>Undo</Button>
          </div>
        )}
      </div>
    </details>
  );
}

/** PRD F17, part 4: each form of the PhD file named as the university's paper names it. */
export function PhdForms({ data, save }: { data: SettingsData; save: Save }) {
  return (
    <Card className="settings-phd-forms">
      <h2>Forms of the PhD file</h2>
      <p className="muted">Give each form your university&apos;s title, form number and “copy to” list. Anything left empty keeps Anveshan&apos;s.</p>
      {Object.entries(data.phd_form_defaults).map(([key, standard]) => (
        <OneForm key={key} formKey={key} standard={standard} saved={data.phd_forms[key]} save={save} />
      ))}
    </Card>
  );
}
