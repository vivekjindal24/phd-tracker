"use client";

import { useState } from "react";
import { DownloadButton } from "@/components/DownloadButton";
import { Card, Field, PageHeader } from "@/components/ui/kit";
import { NotForYourRole } from "@/components/ui/RequireRole";
import { useSession } from "@/lib/session";

const SHEETS = [
  ["projects", "Funded projects and grants received"],
  ["scholars", "PhD scholars registered and awarded per guide"],
  ["publications", "Publications with UGC-CARE, Scopus and WoS indexing"],
  ["books", "Books and chapters"],
] as const;
const YEARS_SHOWN = 12;
const DEFAULT_SPAN = 4;

const label = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, "0")}`;

export default function NaacPage() {
  const { me } = useSession();
  const now = new Date();
  const current = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  const years = Array.from({ length: YEARS_SHOWN }, (_, i) => current - i);
  const [from, setFrom] = useState(current - DEFAULT_SPAN);
  const [to, setTo] = useState(current);

  if (!me?.is_root_admin && !me?.roles.some((r) => r === "research_office" || r === "vice_chancellor")) return <NotForYourRole />;
  const query = `from_year=${from}&to_year=${to}`;
  const select = (value: number, onChange: (y: number) => void) => (
    <select value={value} onChange={(e) => onChange(Number(e.target.value))}>
      {years.map((y) => <option key={y} value={y}>{label(y)}</option>)}
    </select>
  );

  return (
    <>
      <PageHeader eyebrow="Accreditation" title="NAAC Criterion 3 data" />
      <div className="toolbar">
        <Field label="From academic year">{select(from, setFrom)}</Field>
        <Field label="To academic year">{select(to, setTo)}</Field>
      </div>
      <Card>
        <p className="muted">The rows behind each metric, from records already kept. Publications are by calendar year of publication; only approved, published ones appear.</p>
        <ul className="plain-list">
          {SHEETS.map(([key, title]) => (
            <li key={key} className="row">
              <span>{title}</span>
              <DownloadButton path={`/naac/${key}.csv?${query}`}>Download CSV</DownloadButton>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
