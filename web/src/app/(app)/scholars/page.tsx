"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import { STAGES } from "@/lib/types";
import type { Scholar } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

export default function ScholarsPage() {
  const { me } = useSession();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [stage, setStage] = useState("");
  const onlyScholar = me?.roles.length === 1 && me.roles[0] === "scholar";

  useEffect(() => {
    if (onlyScholar && me?.scholar_id) router.replace(`/scholars/${me.scholar_id}`);
  }, [onlyScholar, me, router]);

  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 300); // search as you type, gently
    return () => clearTimeout(t);
  }, [q]);

  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (stage) params.set("stage", stage);
  const { data, error } = useFetch<Scholar[]>(onlyScholar ? null : `/scholars?${params}`);

  if (onlyScholar) return null;
  return (
    <>
      <PageHeader
        eyebrow="Directory"
        title="Scholars"
        actions={
          me?.roles.includes("admin") && (
            <Link href="/people/new" className="btn btn-primary">
              Add person
            </Link>
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
      </div>
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table
          label="Scholars"
          head={["Scholar", "Roll number", "Department", "Stage", "Supervisor"]}
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
    </>
  );
}
