"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { INDEXING_LABELS, PUB_STATUS_LABELS, PUB_TYPE_LABELS } from "@/lib/types";
import type { Indexing, PubStatus, PubType, PublicationContent } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

export const EMPTY_PUBLICATION: PublicationContent = {
  title: "",
  authors: "",
  pub_type: "journal",
  venue: "",
  issn_isbn: null,
  indexing: [],
  doi: null,
  pub_year: new Date().getFullYear(),
  pub_status: "published",
};

export function IndexingChecks({ value, onChange }: { value: Indexing[]; onChange: (v: Indexing[]) => void }) {
  return (
    <fieldset className="check-row">
      <legend>Indexed in</legend>
      {(Object.keys(INDEXING_LABELS) as Indexing[]).map((k) => (
        <label key={k} className="check">
          <input type="checkbox" checked={value.includes(k)}
            onChange={() => onChange(value.includes(k) ? value.filter((v) => v !== k) : [...value, k])} />
          {INDEXING_LABELS[k]}
        </label>
      ))}
    </fieldset>
  );
}

/** The scholar's publication details — used for a new publication and for edits. */
export function PublicationForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial: PublicationContent;
  submitLabel: string;
  onSubmit: (value: PublicationContent) => Promise<void>;
  onCancel?: () => void;
}) {
  const [v, setV] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof PublicationContent>(key: K, value: PublicationContent[K]) =>
    setV((prev) => ({ ...prev, [key]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ ...v, issn_isbn: v.issn_isbn || null, doi: v.doi || null });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <Field label="Title">
        <input required maxLength={500} value={v.title} onChange={(e) => set("title", e.target.value)} />
      </Field>
      <Field label="Authors" hint="In the order printed, e.g. A. Rao, M. Iyer.">
        <input required maxLength={2000} value={v.authors} onChange={(e) => set("authors", e.target.value)} />
      </Field>
      <div className="row">
        <Field label="Type">
          <select value={v.pub_type} onChange={(e) => set("pub_type", e.target.value as PubType)}>
            {(Object.keys(PUB_TYPE_LABELS) as PubType[]).map((k) => <option key={k} value={k}>{PUB_TYPE_LABELS[k]}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={v.pub_status} onChange={(e) => set("pub_status", e.target.value as PubStatus)}>
            {(Object.keys(PUB_STATUS_LABELS) as PubStatus[]).map((k) => <option key={k} value={k}>{PUB_STATUS_LABELS[k]}</option>)}
          </select>
        </Field>
        <Field label="Year">
          <input type="number" required min={1950} max={2100} value={v.pub_year}
            onChange={(e) => set("pub_year", Number(e.target.value))} />
        </Field>
      </div>
      <Field label="Journal / conference / publisher">
        <input required maxLength={500} value={v.venue} onChange={(e) => set("venue", e.target.value)} />
      </Field>
      <div className="row">
        <Field label="ISSN / ISBN">
          <input maxLength={50} value={v.issn_isbn ?? ""} onChange={(e) => set("issn_isbn", e.target.value)} />
        </Field>
        <Field label="DOI" hint="Like 10.1234/abcd.5678">
          <input maxLength={210} pattern="10\.\d{4,9}/\S+" value={v.doi ?? ""} onChange={(e) => set("doi", e.target.value)} />
        </Field>
      </div>
      <IndexingChecks value={v.indexing} onChange={(x) => set("indexing", x)} />
      <ErrorText>{error}</ErrorText>
      <div className="row">
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
        {onCancel && <Button kind="ghost" onClick={onCancel}>Cancel</Button>}
      </div>
    </form>
  );
}
