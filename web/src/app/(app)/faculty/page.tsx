"use client";

import { useState } from "react";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { ListFoot } from "@/components/ListFoot";
import type { Faculty } from "@/lib/types";
import { useDebounced, usePagedFetch } from "@/lib/useFetch";
import { listPath } from "@/components/ScholarFilter";

function Load({ load, max }: { load: number; max: number }) {
  const full = load >= max;
  const pct = max === 0 ? 100 : Math.min(100, (load / max) * 100);
  return (
    <span className={`meter${full ? " meter-full" : ""}`}>
      <span className="meter-track" aria-hidden="true">
        <span className="meter-fill" style={{ width: `${pct}%` }} />
      </span>
      {load}/{max}
      {full && <span className="visually-hidden"> (at their limit)</span>}
    </span>
  );
}

export default function FacultyPage() {
  const [q, setQ] = useState("");
  const query = useDebounced(q);
  const [sort, setSort] = useState("");
  const { data, error, hasMore, more, total, exportPath } = usePagedFetch<Faculty>(
    listPath("/faculty", { q: query, sort }), 200,
  );

  return (
    <>
      <PageHeader eyebrow="Directory" title="Faculty" />
      <div className="toolbar">
        <Field label="Search">
          <input type="search" placeholder="Name" value={q} onChange={(e) => setQ(e.target.value)} />
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Faculty" head={["Name", "Designation", "Department", "Scholars (limit)"]}
          sort={{ by: sort, keys: ["name", "designation", "department", "load"], onChange: setSort }}
          empty={<p className="empty-state">No faculty match.</p>}>
          {data.map((f) => (
            <tr key={f.id}>
              <td>
                <strong>{f.full_name}</strong>
                <br />
                <a href={`mailto:${f.email}`} className="muted">{f.email}</a>
              </td>
              <td>{f.designation}</td>
              <td>{f.unit.name}</td>
              <td>
                {f.can_supervise ? <Load load={f.load} max={f.max_scholars} />
                  : <span className="muted">Not a supervisor</span>}
              </td>
            </tr>
          ))}
        </Table>
      )}
      <ListFoot hasMore={hasMore} more={more} shown={data?.length} total={total} exportPath={exportPath} />
    </>
  );
}
