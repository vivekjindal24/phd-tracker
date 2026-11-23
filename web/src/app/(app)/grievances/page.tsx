"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { ListFoot } from "@/components/ListFoot";
import { api } from "@/lib/api";
import { formatDate, formatDay } from "@/lib/format";
import { useSession } from "@/lib/session";
import { GRIEVANCE_CATEGORY_LABELS, GRIEVANCE_STATUS_LABELS } from "@/lib/types";
import type { Grievance, GrievanceCategory } from "@/lib/types";
import { errorText, usePagedFetch } from "@/lib/useFetch";
import "./grievances.css";

/** The scholar raises a grievance; only the grievance cell (and the VC) will read it. */
function RaiseGrievance() {
  const router = useRouter();
  const [category, setCategory] = useState<GrievanceCategory>("supervision");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const g = await api<Grievance>("/grievances", {
        method: "POST",
        body: JSON.stringify({ category, subject, description }),
      });
      router.push(`/grievances/${g.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2>Raise a grievance</h2>
      <p className="muted">
        Only the university&apos;s grievance cell and the Vice Chancellor read it, never your supervisor or
        department. The cell decides within 15 working days; if you disagree, you may appeal within 15 days.
      </p>
      <p className="grievance-icc">A complaint of sexual harassment goes to the Internal Complaints Committee, not here.</p>
      <form className="stack-form" onSubmit={submit}>
        <div className="row">
          <Field label="About">
            <select value={category} onChange={(e) => setCategory(e.target.value as GrievanceCategory)}>
              {(Object.keys(GRIEVANCE_CATEGORY_LABELS) as GrievanceCategory[]).map((k) => (
                <option key={k} value={k}>{GRIEVANCE_CATEGORY_LABELS[k]}</option>
              ))}
            </select>
          </Field>
          <Field label="Subject">
            <input required maxLength={200} value={subject} onChange={(e) => setSubject(e.target.value)} />
          </Field>
        </div>
        <Field label="What happened" hint="Dates, people and what you have already tried. You can attach papers on the next page.">
          <textarea required maxLength={5000} rows={6} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Filing…" : "File the grievance"}</Button>
      </form>
    </Card>
  );
}

export default function GrievancesPage() {
  const { me } = useSession();
  const { data, error, hasMore, more, total } = usePagedFetch<Grievance>("/grievances", 100);
  const isScholar = me?.scholar_id != null;
  const head = isScholar ? ["Subject", "About", "Status", "Filed"] : ["Subject", "Scholar", "About", "Status", "Due"];

  return (
    <>
      <PageHeader eyebrow="Redressal" title="Grievances" />
      {isScholar && <RaiseGrievance />}
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Grievances" head={head}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No grievances</h2></div>}>
          {data.map((g) => (
            <tr key={g.id}>
              <td><Link href={`/grievances/${g.id}`}>{g.subject}</Link></td>
              {!isScholar && <td>{g.scholar.name}</td>}
              <td>{GRIEVANCE_CATEGORY_LABELS[g.category]}</td>
              <td><span className={`badge grievance-${g.status}`}>{GRIEVANCE_STATUS_LABELS[g.status]}</span></td>
              <td className="mono">{isScholar ? formatDay(g.filed_at) : g.due_on ? formatDate(g.due_on) : "—"}</td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={null} />
    </>
  );
}
