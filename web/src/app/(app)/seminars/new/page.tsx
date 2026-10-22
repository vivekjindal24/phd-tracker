"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import type { Faculty, OrgUnit, Period, Scholar, SeminarDetail } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../seminars.css";

function toggle(list: string[], id: string): string[] {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

export default function ScheduleSeminarPage() {
  const { me } = useSession();
  const router = useRouter();
  const { data: units } = useFetch<OrgUnit[]>("/org-units");
  const { data: faculty } = useFetch<Faculty[]>("/faculty?limit=500");
  // Units this person heads or administers (and everything below them); the API re-checks.
  const myPaths = me?.unit_roles.map((r) => r.unit_path) ?? [];
  const myUnits = (units ?? []).filter((u) => myPaths.some((p) => u.path === p || u.path.startsWith(`${p}.`)));

  const [unitId, setUnitId] = useState("");
  const [title, setTitle] = useState("Six-monthly progress seminar");
  const [startsAt, setStartsAt] = useState("");
  const [venue, setVenue] = useState("");
  const [reportDue, setReportDue] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [period, setPeriod] = useState<Period>(new Date().getMonth() < 6 ? "January-June" : "July-December");
  const [scholarIds, setScholarIds] = useState<string[]>([]);
  const [panelIds, setPanelIds] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!unitId && myUnits.length > 0 && myUnits[0]) setUnitId(myUnits[0].id);
  }, [myUnits, unitId]);
  const { data: scholars } = useFetch<Scholar[]>(unitId ? `/scholars?unit_id=${unitId}&limit=500` : null);
  useEffect(() => setScholarIds([]), [unitId]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api<SeminarDetail>("/seminars", {
        method: "POST",
        body: JSON.stringify({
          unit_id: unitId, title, starts_at: new Date(startsAt).toISOString(), venue,
          report_due: reportDue, report_year: year, period,
          scholar_ids: scholarIds, panel_faculty_ids: panelIds,
        }),
      });
      router.push(`/seminars/${s.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Six-monthly review" title="Schedule a progress seminar" />
      <form className="clay card seminar-form" onSubmit={submit}>
        <div className="two">
          <Field label="Department / unit">
            <select required value={unitId} onChange={(e) => setUnitId(e.target.value)}>
              {myUnits.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </Field>
          <Field label="Title">
            <input required maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} />
          </Field>
        </div>
        <div className="two">
          <Field label="Date & time">
            <input type="datetime-local" required value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
          </Field>
          <Field label="Venue or online link">
            <input maxLength={500} value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="e.g. Seminar hall 2" />
          </Field>
        </div>
        <div className="two">
          <Field label="Report due date" hint="Scholars must submit their progress report in Anveshan by this date.">
            <input type="date" required value={reportDue} onChange={(e) => setReportDue(e.target.value)} />
          </Field>
          <Field label="Reviews the period">
            <div className="row">
              <select value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
                <option value="January-June">January–June</option>
                <option value="July-December">July–December</option>
              </select>
              <input type="number" min={2000} max={2100} value={year} onChange={(e) => setYear(Number(e.target.value))} />
            </div>
          </Field>
        </div>
        <fieldset className="pick-list">
          <legend>Scholars presenting ({scholarIds.length} selected)</legend>
          {(scholars ?? []).map((s) => (
            <label key={s.id}>
              <input type="checkbox" checked={scholarIds.includes(s.id)} onChange={() => setScholarIds(toggle(scholarIds, s.id))} />
              {s.full_name} <span className="muted">({s.roll_number})</span>
            </label>
          ))}
        </fieldset>
        <fieldset className="pick-list">
          <legend>Panel ({panelIds.length} selected)</legend>
          {(faculty ?? []).map((f) => (
            <label key={f.id}>
              <input type="checkbox" checked={panelIds.includes(f.id)} onChange={() => setPanelIds(toggle(panelIds, f.id))} />
              {f.full_name} <span className="muted">· {f.unit.name}</span>
            </label>
          ))}
        </fieldset>
        <p className="muted">Scholars, their supervisors, the HoD/Dean and the panel will be notified.</p>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || scholarIds.length === 0}>
          {busy ? "Scheduling…" : "Schedule and notify"}
        </Button>
      </form>
    </>
  );
}
