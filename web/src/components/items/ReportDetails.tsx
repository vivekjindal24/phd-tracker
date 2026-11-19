"use client";

import { useEffect, useState } from "react";
import { Attachments } from "@/components/Attachments";
import { ReportSections } from "@/components/items/ReportSections";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { Assistantship, ItemView, PeriodActivity, SectionText, SettingsData } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function Activity({ reportId }: { reportId: string }) {
  const { data: a } = useFetch<PeriodActivity>(`/reports/${reportId}/activity`);
  if (!a) return null;
  const list = (items: string[]) => (items.length === 0 ? <span className="muted">None recorded</span> : (
    <ul className="plain-list">{items.map((x) => <li key={x}>{x}</li>)}</ul>
  ));
  return (
    <Card>
      <h2>This period on record</h2>
      <p className="muted">Taken from what is already in the system for these six months.</p>
      <dl className="kv">
        <dt>Supervision meetings</dt><dd>{a.meetings}</dd>
        {a.publications && (<><dt>Publications this year</dt><dd>{list(a.publications)}</dd></>)}
        {a.conferences && (<><dt>Conferences and talks</dt><dd>{list(a.conferences)}</dd></>)}
      </dl>
    </Card>
  );
}

const ASSISTANTSHIP_TEXT: Record<Assistantship, string> = {
  with: "May continue with the programme with assistantship",
  without: "May continue with the programme without assistantship",
};

/** The committee's recommendation line (printed on the PDF): stated by whoever acts at the
 *  current step, before they approve; read by everyone else. */
function AssistantshipLine({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const value = (item.content.assistantship ?? null) as Assistantship | null;
  const [error, setError] = useState<string | null>(null);
  if (!item.can_act && !value) return null;

  async function set(next: string) {
    setError(null);
    try {
      onSaved(await api<ItemView>(`/reports/${item.id}/assistantship`, {
        method: "PUT",
        body: JSON.stringify({ assistantship: next || null }),
      }));
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <Card>
      <h2>Recommendation</h2>
      {item.can_act ? (
        <Field label="Assistantship" hint="Printed on the report as the committee's recommendation.">
          <select value={value ?? ""} onChange={(e) => set(e.target.value)}>
            <option value="">Not stated</option>
            {(Object.keys(ASSISTANTSHIP_TEXT) as Assistantship[]).map((k) => <option key={k} value={k}>{ASSISTANTSHIP_TEXT[k]}</option>)}
          </select>
        </Field>
      ) : (
        <p>{value && ASSISTANTSHIP_TEXT[value]}</p>
      )}
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}

/** A progress report: the summary, the template's sections, its files and the period's activity. */
export function ReportDetails({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const summary = String(item.content.summary ?? "");
  const sections = (item.content.sections ?? []) as SectionText[];
  const template = useFetch<SettingsData>(item.can_edit ? "/settings" : null).data?.apr_template;
  const [draft, setDraft] = useState(summary);
  const [parts, setParts] = useState(sections);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { setDraft(summary); setParts(sections); }, [item]); // eslint-disable-line react-hooks/exhaustive-deps

  async function save() {
    setError(null);
    try {
      onSaved(await api<ItemView>(`/reports/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify({ summary: draft, sections: parts }),
      }));
      setEditing(false);
    } catch (e) {
      setError(errorText(e));
    }
  }

  const missing = (template ?? []).filter((t) => !sections.some((s) => s.name === t.name && s.text.trim()));
  return (
    <>
      <Card>
        <h2>Progress report</h2>
        {editing && template ? (
          <>
            <Field label="Summary" hint="A short overview, at least 20 characters.">
              <textarea className="summary-edit" value={draft} maxLength={20000} onChange={(e) => setDraft(e.target.value)} />
            </Field>
            <ReportSections template={template} value={parts} onChange={setParts} />
          </>
        ) : (
          <>
            <h3>Summary</h3>
            <p className="prose">{summary}</p>
            {sections.filter((s) => s.text.trim()).map((s) => (
              <section key={s.name}>
                <h3>{s.name}</h3>
                <p className="prose">{s.text}</p>
              </section>
            ))}
            {item.can_edit && missing.length > 0 && (
              <p className="muted">Still to write before you can submit: {missing.map((m) => m.name).join(", ")}.</p>
            )}
          </>
        )}
        <ErrorText>{error}</ErrorText>
        {item.can_edit && (editing ? (
          <div className="row">
            <Button kind="primary" onClick={save}>Save</Button>
            <Button kind="ghost" onClick={() => { setDraft(summary); setParts(sections); setEditing(false); }}>Cancel</Button>
          </div>
        ) : (
          <Button onClick={() => setEditing(true)}>Edit report</Button>
        ))}
      </Card>
      <AssistantshipLine item={item} onSaved={onSaved} />
      <Attachments table="progress_reports" recordId={item.id} canUpload={item.can_edit}
        hint="The full report, slides, data or anything else the approvers should read." />
      <Activity reportId={item.id} />
    </>
  );
}
