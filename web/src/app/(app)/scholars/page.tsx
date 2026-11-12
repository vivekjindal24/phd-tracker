"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { ListFoot } from "@/components/ListFoot";
import { useSession } from "@/lib/session";
import { STAGES, STUDY_MODE_LABELS } from "@/lib/types";
import type { Scholar } from "@/lib/types";
import { useDebounced, usePagedFetch } from "@/lib/useFetch";

export default function ScholarsPage() {
  const { me } = useSession();
  const router = useRouter();
  const [q, setQ] = useState("");
  const query = useDebounced(q);
  const [stage, setStage] = useState("");
  const [mode, setMode] = useState("");
  const onlyScholar = me?.roles.length === 1 && me.roles[0] === "scholar";

  useEffect(() => {
    if (onlyScholar && me?.scholar_id) router.replace(`/scholars/${me.scholar_id}`);
  }, [onlyScholar, me, router]);

  const [sort, setSort] = useState("");
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (stage) params.set("stage", stage);
  if (mode) params.set("study_mode", mode);
  if (sort) params.set("sort", sort);
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<Scholar>(onlyScholar ? null : `/scholars?${params}`, 100);

  if (onlyScholar) return null;
  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Scholars"
        actions={
          me?.roles.includes("admin") && (
            <>
              <Link href="/people/import" className="btn btn-secondary">
                Import from Excel
              </Link>
              <Link href="/people/new" className="btn btn-primary">
                Add person
              </Link>
            </>
          )
        }
      />
      <div className="toolbar">
        <Field label="Search">
          <input type="search" placeholder="Name, roll number or title" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </Field>
        <Field label="Stage">
          <select value={stage} onChange={(e) => setStage(e.target.value)}>
            <option value="">All stages</option>
            {STAGES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field label="Mode">
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">Any</option>
            {Object.entries(STUDY_MODE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table
          label="Scholars"
          head={["Scholar", "Roll number", "Department", "Stage", "Supervisor"]}
          sort={{ by: sort, keys: ["name", "roll_number", "department", "stage", "supervisor"], onChange: setSort }}
          empty={
            <div className="empty-state">
              <Owl pose="empty" size={96} />
              <p>No scholars match.</p>
            </div>
          }
        >
          {data.map((s) => (
            <tr key={s.id}>
              <td>
                <Link href={`/scholars/${s.id}`}>{s.full_name}</Link>
              </td>
              <td className="mono">{s.roll_number}</td>
              <td>{s.unit.name}</td>
              <td>
                <span className="badge">{s.stage}</span>
              </td>
              <td>{s.supervisor?.name ?? <span className="muted">Not assigned</span>}</td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}
