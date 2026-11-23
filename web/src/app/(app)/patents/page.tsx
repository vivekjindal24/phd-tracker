"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { ListFoot } from "@/components/ListFoot";
import { listPath, useScholarFilter } from "@/components/ScholarFilter";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { PATENT_CHECK_LABELS, PATENT_STATUS_LABELS, VERIFICATION_BADGE } from "@/lib/types";
import type { PatentRow, PatentStatus, Verification } from "@/lib/types";
import { usePagedFetch } from "@/lib/useFetch";

/** Patents (PRD M10): the author's own, and those the reader may see (scope.patent_predicate).
 *  Home links here with ?verification=. */
function Patents() {
  const { me } = useSession();
  const filter = useScholarFilter("Name, title or application number");
  const [verification, setVerification] = useState(useSearchParams().get("verification") ?? "");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("");
  const filtered = filter.active || Boolean(verification || status);
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<PatentRow>(
    listPath("/patents", filter.params, { verification, patent_status: status, sort }), 200);
  const author = me?.faculty_id != null || me?.scholar_id != null;

  return (
    <>
      <PageHeader eyebrow="Research record" title="Patents"
        actions={author && <Link href="/patents/new" className="btn btn-primary">Add your patent</Link>} />
      <p className="muted">A patent counts in the NAAC data once it has been checked and verified.</p>
      <div className="toolbar">
        {filter.fields}
        <Field label="Checked">
          <select value={verification} onChange={(e) => setVerification(e.target.value)}>
            <option value="">All</option>
            {(Object.keys(PATENT_CHECK_LABELS) as Verification[]).map((v) => <option key={v} value={v}>{PATENT_CHECK_LABELS[v]}</option>)}
          </select>
        </Field>
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Any</option>
            {(Object.keys(PATENT_STATUS_LABELS) as PatentStatus[]).map((s) => <option key={s} value={s}>{PATENT_STATUS_LABELS[s]}</option>)}
          </select>
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Patents" head={["Title", "Inventor", "Filed", "Status", "Checked"]}
          sort={{ by: sort, keys: ["title", "owner", "filed_on", "status", "verification"], onChange: setSort }}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <h2>{filtered ? "No patents match" : "No patents yet"}</h2>
              <p>{filtered ? "Try a different search or status." : author ? "Add a patent you have filed." : "They appear here once members of faculty and scholars add them."}</p>
            </div>
          }>
          {data.map((p) => (
            <tr key={p.id}>
              <td><Link href={`/patents/${p.id}`}>{p.title}</Link>
                <div className="muted mono">{p.application_number}</div></td>
              <td>{p.owner.name}<div className="muted">{p.owner_kind === "scholar" ? "Scholar" : "Faculty"} · {p.unit}</div></td>
              <td>{formatDate(p.filed_on)}</td>
              <td>{PATENT_STATUS_LABELS[p.patent_status]}{p.granted_on && <div className="muted">{formatDate(p.granted_on)}</div>}</td>
              <td><span className={`badge ${VERIFICATION_BADGE[p.verification]}`}>{PATENT_CHECK_LABELS[p.verification]}</span></td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}

export default function PatentsPage() {
  return <Suspense><Patents /></Suspense>;
}
