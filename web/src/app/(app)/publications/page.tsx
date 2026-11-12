"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { listPath, useScholarFilter } from "@/components/ScholarFilter";
import { StateBadge } from "@/components/items/StateBadge";
import { ErrorText, Field, PageHeader, ShowMore, Table } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import { INDEXING_LABELS, PUB_TYPE_LABELS, STATE_LABELS } from "@/lib/types";
import type { ItemState, PublicationRow } from "@/lib/types";
import { usePagedFetch } from "@/lib/useFetch";

export default function PublicationsPage() {
  const { me } = useSession();
  const filter = useScholarFilter("Scholar name, roll number or title");
  const [state, setState] = useState("");
  const [year, setYear] = useState("");
  const filtered = filter.active || Boolean(state || year);
  const [sort, setSort] = useState("");
  const { data, error, hasMore, more } = usePagedFetch<PublicationRow>(
    listPath("/publications", filter.params, { state, pub_year: year, sort }), 500);
  const isScholar = me?.scholar_id != null;

  return (
    <>
      <PageHeader eyebrow="Research record" title="Publications"
        actions={isScholar && <Link href="/publications/new" className="btn btn-primary">Add publication</Link>} />
      <div className="toolbar">
        {filter.fields}
        <Field label="State">
          <select value={state} onChange={(e) => setState(e.target.value)}>
            <option value="">All</option>
            {(Object.keys(STATE_LABELS) as ItemState[]).map((s) => <option key={s} value={s}>{STATE_LABELS[s]}</option>)}
          </select>
        </Field>
        <Field label="Year">
          <input type="number" min={1950} max={2100} placeholder="Any" value={year}
            onChange={(e) => setYear(e.target.value)} />
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Publications" head={["Title", "Scholar", "Venue", "Indexed", "State"]}
          sort={{ by: sort, keys: ["title", "scholar", "venue", null, "state"], onChange: setSort }}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>{filtered ? "No publications match" : "No publications yet"}</h2>
              <p>{filtered ? "Try a different search, state or year." : isScholar ? "Add a paper and send it for verification." : "Publications appear here once scholars add them."}</p>
            </div>
          }>
          {data.map((p) => (
            <tr key={p.id}>
              <td><Link href={`/items/publication/${p.id}`}>{p.title}</Link>
                <div className="muted">{PUB_TYPE_LABELS[p.pub_type]} · {p.pub_year}</div></td>
              <td>{p.scholar.name}</td>
              <td>{p.venue}</td>
              <td>{p.indexing.map((i) => INDEXING_LABELS[i]).join(", ") || "—"}</td>
              <td><StateBadge state={p.state} waitingOn={p.waiting_on} /></td>
            </tr>
          ))}
        </Table>
      )}
      <ShowMore hasMore={hasMore} more={more} />
    </>
  );
}
