"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Owl } from "@/components/brand/Owl";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatDate, formatMoney } from "@/lib/format";
import { useSession } from "@/lib/session";
import { PROJECT_STATUS_LABELS } from "@/lib/types";
import type { Faculty, Project } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

function NewProject() {
  const router = useRouter();
  const { data: faculty } = useFetch<Faculty[]>("/faculty?limit=500");
  const [v, setV] = useState({ pi_id: "", agency: "", title: "", sanction_number: "", amount_sanctioned: "", start_date: "", end_date: "" });
  const [error, setError] = useState<string | null>(null);
  const set = (k: keyof typeof v, value: string) => setV((p) => ({ ...p, [k]: value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const p = await api<Project>("/projects", { method: "POST", body: JSON.stringify({ ...v, amount_sanctioned: Number(v.amount_sanctioned) }) });
      router.push(`/projects/${p.id}`);
    } catch (err) {
      setError(errorText(err));
    }
  }

  return (
    <Card>
      <h2>Record a project</h2>
      <form className="stack-form" onSubmit={submit}>
        <Field label="Title"><input required maxLength={500} value={v.title} onChange={(e) => set("title", e.target.value)} /></Field>
        <div className="row">
          <Field label="Principal investigator" hint="The project belongs to their department">
            <select required value={v.pi_id} onChange={(e) => set("pi_id", e.target.value)}>
              <option value="" disabled>Choose…</option>
              {faculty?.map((f) => <option key={f.id} value={f.id}>{f.full_name} · {f.unit.name}</option>)}
            </select>
          </Field>
          <Field label="Funding agency" hint="DST, SERB, ICSSR, …"><input required maxLength={200} value={v.agency} onChange={(e) => set("agency", e.target.value)} /></Field>
        </div>
        <div className="row">
          <Field label="Sanction number"><input required maxLength={100} value={v.sanction_number} onChange={(e) => set("sanction_number", e.target.value)} /></Field>
          <Field label="Amount sanctioned (₹)"><input type="number" required min={0} step={1} value={v.amount_sanctioned} onChange={(e) => set("amount_sanctioned", e.target.value)} /></Field>
        </div>
        <div className="row">
          <Field label="Starts"><input type="date" required value={v.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
          <Field label="Ends"><input type="date" required value={v.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
        </div>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit">Save project</Button>
      </form>
    </Card>
  );
}

export default function ProjectsPage() {
  const { me } = useSession();
  const { data, error } = useFetch<Project[]>("/projects");
  const canRecord = me ? me.office_roles.includes("research_office") || me.unit_roles.some((r) => r.role === "admin") : false;

  return (
    <>
      <PageHeader eyebrow="Grants" title="Research projects" />
      <ErrorText>{error}</ErrorText>
      {data && (
        <Table label="Research projects" head={["Project", "Agency", "PI", "Sanctioned", "Period", "Status"]}
          empty={<div className="empty-state"><Owl pose="empty" size={96} /><h2>No projects yet</h2></div>}>
          {data.map((p) => (
            <tr key={p.id}>
              <td><Link href={`/projects/${p.id}`}>{p.title}</Link><div className="muted mono">{p.sanction_number}</div></td>
              <td>{p.agency}</td>
              <td>{p.pi.name}<div className="muted">{p.unit.name}</div></td>
              <td className="mono">{formatMoney(p.amount_sanctioned)}</td>
              <td className="mono">{formatDate(p.start_date)} – {formatDate(p.end_date)}</td>
              <td>{PROJECT_STATUS_LABELS[p.status]}</td>
            </tr>
          ))}
        </Table>
      )}
      {canRecord && <NewProject />}
    </>
  );
}
