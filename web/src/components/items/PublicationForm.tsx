"use client";

import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Button, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { doiFromPdf } from "@/lib/pdfDoi";
import { INDEXING_LABELS, PUB_STATUS_LABELS, PUB_TYPE_LABELS } from "@/lib/types";
import type { DoiDetails, Indexing, PubStatus, PubType, PublicationContent } from "@/lib/types";
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

/** Paste a DOI, or choose the paper's PDF and its DOI is read from it, and Crossref fills the
 *  rest of the form; the author checks it before saving. A chosen PDF is attached on saving. */
function DoiFill({ base, onFound, onPaper }: {
  base: string;
  onFound: (d: DoiDetails) => void;
  onPaper?: (file: File) => void;
}) {
  const [q, setQ] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function fill(doi = q) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const d = await api<DoiDetails>(`${base}/doi?q=${encodeURIComponent(doi)}`);
      onFound(d);
      setNote(d.already_recorded
        ? "Filled in from Crossref, but you have already recorded a publication with this DOI."
        : "Filled in from Crossref. Check every field, and tick the indexing yourself: Crossref does not know it.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function readPaper(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !onPaper) return;
    setError(null);
    setNote(null);
    if (file.type !== "application/pdf") {
      setError("Choose the paper as a PDF.");
      return;
    }
    onPaper(file);
    setBusy(true);
    let doi: string | null;
    try {
      doi = await doiFromPdf(file);
    } catch {
      doi = null; // a damaged or protected PDF: said below, the file is still attached
    } finally {
      setBusy(false);
    }
    if (doi) {
      setQ(doi);
      await fill(doi);
    } else {
      setNote("No DOI found in this PDF (a scanned copy has no text to read). Paste the DOI above, or fill in the fields yourself. The PDF is still attached when you save.");
    }
  }

  return (
    <div className="stack-form">
      {onPaper && (
        <Field label="Start from the paper" hint="Choose the published paper (PDF). Its DOI is read from it to fill in the form, and it is attached when you save.">
          <input type="file" accept="application/pdf" disabled={busy} onChange={readPaper} />
        </Field>
      )}
      <div className="row">
        <Field label="Fill in from the DOI" hint="Paste the DOI or its doi.org link.">
          <input maxLength={300} value={q} placeholder="10.1234/abcd.5678" onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (q.trim()) fill(); } }} />
        </Field>
        <Button kind="secondary" disabled={busy || !q.trim()} onClick={() => fill()}>{busy ? "Looking up…" : "Fill in"}</Button>
      </div>
      {note && <p className="muted" role="status">{note}</p>}
      <ErrorText>{error}</ErrorText>
    </div>
  );
}

/** A paper's details — new or edited, a scholar's (`/publications`) or faculty's
 *  (`/faculty-publications`); `base` is the list whose DOI lookup the form uses. With
 *  `withPaper` (a new record) the author may start from the PDF, handed to `onSubmit`. */
export function PublicationForm({
  initial,
  submitLabel,
  onSubmit,
  onCancel,
  base = "/publications",
  withPaper = false,
}: {
  base?: string;
  initial: PublicationContent;
  submitLabel: string;
  onSubmit: (value: PublicationContent, paper: File | null) => Promise<void>;
  onCancel?: () => void;
  withPaper?: boolean;
}) {
  const [v, setV] = useState(initial);
  const [paper, setPaper] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof PublicationContent>(key: K, value: PublicationContent[K]) =>
    setV((prev) => ({ ...prev, [key]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit({ ...v, issn_isbn: v.issn_isbn || null, doi: v.doi || null }, paper);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack-form" onSubmit={submit}>
      <DoiFill base={base} onPaper={withPaper ? setPaper : undefined}
        onFound={({ already_recorded: _, pub_year, issn_isbn, ...d }) =>
          setV((prev) => ({ ...prev, ...d, issn_isbn: issn_isbn ?? prev.issn_isbn, pub_year: pub_year ?? prev.pub_year }))} />
      {paper && (
        <p className="row" role="status">
          <span>Attached when you save: <strong>{paper.name}</strong></span>
          <Button kind="ghost" onClick={() => setPaper(null)}>Don&apos;t attach</Button>
        </p>
      )}
      <Field label="Title">
        <input required maxLength={500} value={v.title} onChange={(e) => set("title", e.target.value)} />
      </Field>
      <Field label="Authors" hint="In the order printed, e.g. A. Rao, M. Iyer.">
        <input required maxLength={2000} value={v.authors} onChange={(e) => set("authors", e.target.value)} />
      </Field>
      <div className="row">
        <Field label="Type">
          <select value={v.pub_type} onChange={(e) => set("pub_type", e.target.value as PubType)}>
            {/* Patents are their own record now (Research → Patents); the type stays only for old papers. */}
            {(Object.keys(PUB_TYPE_LABELS) as PubType[]).filter((k) => k !== "patent").map((k) => <option key={k} value={k}>{PUB_TYPE_LABELS[k]}</option>)}
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
