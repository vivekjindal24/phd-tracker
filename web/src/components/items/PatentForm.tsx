"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { PATENT_STATUS_LABELS } from "@/lib/types";
import type { PatentContent, PatentStatus } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

export const EMPTY_PATENT: PatentContent = {
  title: "",
  inventors: "",
  application_number: "",
  filed_on: "",
  office: "Indian Patent Office",
  patent_status: "filed",
  published_on: null,
  granted_on: null,
  patent_number: null,
};

/** A patent's details, new or updated. Dates past the status are cleared on save, so a filed
 *  patent never carries a grant date; the API checks the rest (PatentIn). */
export function PatentForm({ initial, submitLabel, onSubmit, onCancel }: {
  initial: PatentContent;
  submitLabel: string;
  onSubmit: (value: PatentContent) => Promise<void>;
  onCancel?: () => void;
}) {
  const [v, setV] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof PatentContent>(key: K, value: PatentContent[K]) => setV((prev) => ({ ...prev, [key]: value }));
  const published = v.patent_status !== "filed";
  const granted = v.patent_status === "granted";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({
        ...v,
        published_on: published ? v.published_on || null : null,
        granted_on: granted ? v.granted_on || null : null,
        patent_number: granted ? v.patent_number || null : null,
      });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <Field label="Title of the invention">
        <input required maxLength={500} value={v.title} onChange={(e) => set("title", e.target.value)} />
      </Field>
      <Field label="Inventors" hint="In the order on the application, e.g. M. Krishnan, P. Sharma.">
        <input required maxLength={2000} value={v.inventors} onChange={(e) => set("inventors", e.target.value)} />
      </Field>
      <div className="row">
        <Field label="Application number">
          <input required maxLength={100} value={v.application_number} onChange={(e) => set("application_number", e.target.value)} />
        </Field>
        <Field label="Filed on">
          <input type="date" required value={v.filed_on} onChange={(e) => set("filed_on", e.target.value)} />
        </Field>
        <Field label="Patent office">
          <input required maxLength={100} value={v.office} onChange={(e) => set("office", e.target.value)} />
        </Field>
      </div>
      <div className="row">
        <Field label="Status">
          <select value={v.patent_status} onChange={(e) => set("patent_status", e.target.value as PatentStatus)}>
            {(Object.keys(PATENT_STATUS_LABELS) as PatentStatus[]).map((k) => <option key={k} value={k}>{PATENT_STATUS_LABELS[k]}</option>)}
          </select>
        </Field>
        {published && (
          <Field label="Published on" hint="In the patent office journal.">
            <input type="date" required={v.patent_status === "published"} min={v.filed_on || undefined}
              value={v.published_on ?? ""} onChange={(e) => set("published_on", e.target.value)} />
          </Field>
        )}
        {granted && (
          <>
            <Field label="Granted on">
              <input type="date" required min={v.filed_on || undefined} value={v.granted_on ?? ""} onChange={(e) => set("granted_on", e.target.value)} />
            </Field>
            <Field label="Patent number">
              <input required maxLength={100} value={v.patent_number ?? ""} onChange={(e) => set("patent_number", e.target.value)} />
            </Field>
          </>
        )}
      </div>
      <ErrorText>{error}</ErrorText>
      <div className="row">
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
        {onCancel && <Button kind="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}
