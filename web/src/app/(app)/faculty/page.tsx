"use client";

import { useEffect, useState } from "react";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import type { Faculty } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

function Load({ load, max }: { load: number; max: number }) {
  const full = load >= max;
  const pct = max === 0 ? 100 : Math.min(100, (load / max) * 100);
  return (
    <span className={`meter${full ? " meter-full" : ""}`}>
      <span className="meter-track" aria-hidden="true">
        <span className="meter-fill" style={{ width: `${pct}%` }} />
      </span>
      {load}/{max}
      {full && <span className="visually-hidden"> (at UGC limit)</span>}
    </span>
  );
}

export default function FacultyPage() {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);
  const { data, error } = useFetch<Faculty[]>(
    `/faculty${query ? `?q=${encodeURIComponent(query)}` : ""}`,
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
        <Table label="Faculty" head={["Name", "Designation", "Department", "Scholars (UGC limit)"]}
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
    </>
  );
}
