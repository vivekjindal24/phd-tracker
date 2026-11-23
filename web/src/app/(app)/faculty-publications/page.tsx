"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { ListFoot } from "@/components/ListFoot";
import { listPath, useScholarFilter } from "@/components/ScholarFilter";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import { INDEXING_LABELS, PUB_TYPE_LABELS, VERIFICATION_BADGE, VERIFICATION_LABELS } from "@/lib/types";
import type { FacultyPublicationRow, Indexing, Verification } from "@/lib/types";
import { usePagedFetch } from "@/lib/useFetch";

/** Faculty papers (PRD M1): an author sees their own; the Library, heads and offices those
 *  they may read (scope.faculty_publication_predicate). Home links here with ?verification=. */
function FacultyPublications() {
  const { me } = useSession();
  const filter = useScholarFilter("Name, title or journal");
  const [verification, setVerification] = useState(useSearchParams().get("verification") ?? "");
  const [year, setYear] = useState("");
  const [indexing, setIndexing] = useState("");
  const [sort, setSort] = useState("");
  const filtered = filter.active || Boolean(verification || year || indexing);
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<FacultyPublicationRow>(
    listPath("/faculty-publications", filter.params, { verification, pub_year: year, indexing, sort }), 200);
  const isFaculty = me?.faculty_id != null;
  const isLibrary = me?.roles.includes("library") ?? false;
  const mine = (r: FacultyPublicationRow) => r.faculty.id === me?.faculty_id;

  return (
    <>
      <PageHeader eyebrow="Research record" title="Faculty publications"
        actions={isFaculty && <Link href="/faculty-publications/new" className="btn btn-primary">Add your publication</Link>} />
      <p className="muted">
        {isLibrary
          ? "Papers members of faculty have recorded. Verify each one's indexing and DOI, or return it with a note."
          : "A paper counts in the NAAC data once the Library has verified it."}
      </p>
      <div className="toolbar">
        {filter.fields}
        <Field label="Library">
          <select value={verification} onChange={(e) => setVerification(e.target.value)}>
            <option value="">All</option>
            {(Object.keys(VERIFICATION_LABELS) as Verification[]).map((v) => <option key={v} value={v}>{VERIFICATION_LABELS[v]}</option>)}
          </select>
        </Field>
        <Field label="Indexed in">
          <select value={indexing} onChange={(e) => setIndexing(e.target.value)}>
            <option value="">Any</option>
            {(Object.keys(INDEXING_LABELS) as Indexing[]).map((i) => <option key={i} value={i}>{INDEXING_LABELS[i]}</option>)}
          </select>
        </Field>
        <Field label="Year">
          <input type="number" min={1950} max={2100} placeholder="Any" value={year}
            onChange={(e) => setYear(e.target.value)} />
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Faculty publications" head={["Title", "Faculty", "Venue", "Indexed", "Library"]}
          sort={{ by: sort, keys: ["title", "faculty", "venue", null, "verification"], onChange: setSort }}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>{filtered ? "No publications match" : "No faculty publications yet"}</h2>
              <p>{filtered ? "Try a different search, state or year." : isFaculty ? "Add a paper, or import them all from ORCID." : "They appear here once members of faculty add them."}</p>
            </div>
          }>
          {data.map((p) => (
            <tr key={p.id}>
              <td><Link href={`/faculty-publications/${p.id}`}>{p.title}</Link>
                <div className="muted">{PUB_TYPE_LABELS[p.pub_type]} · {p.pub_year}</div></td>
              <td>{p.faculty.name}<div className="muted">{p.unit}</div></td>
              <td>{p.venue}</td>
              <td>{p.indexing.map((i) => INDEXING_LABELS[i]).join(", ") || "—"}</td>
              <td>
                <span className={`badge ${VERIFICATION_BADGE[p.verification]}`}>
                  {p.verification === "returned" && !mine(p) ? "Returned" : VERIFICATION_LABELS[p.verification]}
                </span>
              </td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}

export default function FacultyPublicationsPage() {
  return <Suspense><FacultyPublications /></Suspense>;
}
