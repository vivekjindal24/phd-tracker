"use client";

import { useState } from "react";
import { Button, Card, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { INDEXING_LABELS, PUB_STATUS_LABELS, PUB_TYPE_LABELS } from "@/lib/types";
import type { Indexing, ItemView, PublicationContent } from "@/lib/types";
import { errorText } from "@/lib/useFetch";
import { IndexingChecks, PublicationForm } from "./PublicationForm";

function safeDoiUrl(doi: string): string {
  return `https://doi.org/${encodeURIComponent(doi).replace(/%2F/g, "/")}`;
}

/** The Library confirms indexing and DOI at its step, before approving (PRD M1). */
function Verification({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as PublicationContent;
  const [indexing, setIndexing] = useState<Indexing[]>(c.indexing);
  const [doi, setDoi] = useState(c.doi ?? "");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function save() {
    setError(null);
    try {
      onSaved(await api<ItemView>(`/publications/${item.id}/verification`, {
        method: "PUT",
        body: JSON.stringify({ indexing, doi: doi || null }),
      }));
      setSaved(true);
    } catch (e) {
      setError(errorText(e));
    }
  }

  return (
    <div className="verify">
      <h3>Library verification</h3>
      <p className="muted">Correct the indexing and DOI to what you checked (Scopus / Web of Science / UGC-CARE list), save, then approve.</p>
      <IndexingChecks value={indexing} onChange={setIndexing} />
      <label className="field">
        DOI
        <input value={doi} maxLength={210} onChange={(e) => setDoi(e.target.value)} />
      </label>
      <ErrorText>{error}</ErrorText>
      {saved && <p className="muted" role="status">Saved.</p>}
      <Button kind="secondary" onClick={save}>Save verification</Button>
    </div>
  );
}

export function PublicationDetails({ item, onSaved }: { item: ItemView; onSaved: (v: ItemView) => void }) {
  const c = item.content as PublicationContent;
  const [editing, setEditing] = useState(false);

  if (editing) {
    return (
      <Card>
        <h2>Edit publication</h2>
        <PublicationForm initial={c} submitLabel="Save" onCancel={() => setEditing(false)}
          onSubmit={async (value) => {
            onSaved(await api<ItemView>(`/publications/${item.id}`, { method: "PATCH", body: JSON.stringify(value) }));
            setEditing(false);
          }} />
      </Card>
    );
  }
  return (
    <Card>
      <h2>Publication</h2>
      <dl className="kv">
        <dt>Authors</dt><dd>{c.authors}</dd>
        <dt>Type</dt><dd>{PUB_TYPE_LABELS[c.pub_type]} · {PUB_STATUS_LABELS[c.pub_status]} · {c.pub_year}</dd>
        <dt>Venue</dt><dd>{c.venue}{c.issn_isbn && <span className="muted"> · {c.issn_isbn}</span>}</dd>
        <dt>Indexed in</dt>
        <dd>{c.indexing.length ? c.indexing.map((i) => INDEXING_LABELS[i]).join(", ") : <span className="muted">Not indexed</span>}</dd>
        <dt>DOI</dt>
        <dd>{c.doi ? <a href={safeDoiUrl(c.doi)} target="_blank" rel="noopener noreferrer">{c.doi}</a> : <span className="muted">None</span>}</dd>
      </dl>
      {item.can_edit && <Button onClick={() => setEditing(true)}>Edit details</Button>}
      {item.can_act && item.waiting_on === "Library" && <Verification item={item} onSaved={onSaved} />}
    </Card>
  );
}
