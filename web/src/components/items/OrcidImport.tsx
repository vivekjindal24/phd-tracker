"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { DoiImportOut, OrcidWork } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

const MAX_IMPORT = 50; // the API takes at most this many DOIs at once

function note(w: OrcidWork): string | null {
  if (!w.doi) return "No DOI: add it by hand";
  if (w.already_recorded) return "Already recorded";
  return null;
}

/** Works from the author's public ORCID record, brought in through their DOIs: a scholar's as
 *  drafts (`/publications`), faculty's straight to the Library (`/faculty-publications`). */
export function OrcidImport({ base = "/publications" }: { base?: string }) {
  const toLibrary = base === "/faculty-publications";
  const [id, setId] = useState("");
  const [works, setWorks] = useState<OrcidWork[] | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<DoiImportOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(task: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await task();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  function list(e: FormEvent) {
    e.preventDefault();
    run(async () => {
      const found = await api<OrcidWork[]>(`${base}/orcid?q=${encodeURIComponent(id)}`);
      setWorks(found);
      setResult(null);
      setChosen(new Set(found.filter((w) => !note(w)).slice(0, MAX_IMPORT).map((w) => w.doi as string)));
    });
  }

  function toggle(doi: string) {
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(doi)) next.delete(doi);
      else if (next.size < MAX_IMPORT) next.add(doi);
      return next;
    });
  }

  function bringIn() {
    run(async () => {
      setResult(await api<DoiImportOut>(`${base}/import`, {
        method: "POST",
        body: JSON.stringify({ dois: [...chosen] }),
      }));
      setWorks(null);
    });
  }

  return (
    <Card>
      <h2>Import from ORCID</h2>
      <p className="muted">{toLibrary
        ? "Bring in all your papers at once. Each one with a DOI is filled in from Crossref and goes to the Library to verify; open each to check it, tick where it is indexed and attach the paper."
        : "Bring in all your papers at once. Each one with a DOI is filled in from Crossref and saved as a draft; check it, tick where it is indexed, attach the paper and submit it."}</p>
      <form className="row" onSubmit={list}>
        <Field label="Your ORCID iD" hint="Like 0000-0002-1825-0097, or your orcid.org link.">
          <input required maxLength={100} value={id} onChange={(e) => setId(e.target.value)} />
        </Field>
        <Button kind="secondary" type="submit" disabled={busy}>{busy && !works ? "Looking up…" : "Show my works"}</Button>
      </form>
      <ErrorText>{error}</ErrorText>
      {works && (
        <>
          <Table label="Works on ORCID" head={["", "Title", "Year", "DOI"]}
            empty={<p className="muted">Your public ORCID record lists no works.</p>}>
            {works.map((w) => (
              <tr key={w.put_code}>
                <td>
                  <input type="checkbox" aria-label={`Import ${w.title}`} disabled={!!note(w)}
                    checked={!!w.doi && chosen.has(w.doi)} onChange={() => w.doi && toggle(w.doi)} />
                </td>
                <td>{w.title}{note(w) && <> <span className="muted">· {note(w)}</span></>}</td>
                <td className="mono">{w.year ?? "—"}</td>
                <td className="mono">{w.doi ?? "—"}</td>
              </tr>
            ))}
          </Table>
          <Button kind="primary" disabled={busy || chosen.size === 0} onClick={bringIn}>
            {busy ? "Importing…" : toLibrary ? `Import ${chosen.size}` : `Import ${chosen.size} as drafts`}
          </Button>
        </>
      )}
      {result && (
        <div role="status">
          <p>{result.created.length} {toLibrary ? "paper" : "draft"}{result.created.length === 1 ? "" : "s"} added. <Link href={base}>See your publications</Link></p>
          {result.skipped.length > 0 && (
            <ul>{result.skipped.map((s) => <li key={s.doi}><span className="mono">{s.doi}</span>: {s.reason}</li>)}</ul>
          )}
        </div>
      )}
    </Card>
  );
}
