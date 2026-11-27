"use client";

import { PersonChecks } from "@/components/PersonPicker";
import { RequireRole } from "@/components/ui/RequireRole";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { SEMINAR_KIND_LABELS } from "@/lib/types";
import type { CommitteeView, Faculty, OrgUnit, Period, Scholar, SeminarDetail, SeminarKind } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../seminars.css";

function ScheduleSeminarForm() {
  const { me } = useSession();
  const router = useRouter();
  const { data: units } = useFetch<OrgUnit[]>("/org-units");
  // Units this person heads or administers (and everything below them); the API re-checks.
  const myPaths = me?.unit_roles.map((r) => r.unit_path) ?? [];
  const myUnits = (units ?? []).filter((u) => myPaths.some((p) => u.path === p || u.path.startsWith(`${p}.`)));

  const [unitId, setUnitId] = useState("");
  const [kind, setKind] = useState<SeminarKind>("progress");
  const [typedTitle, setTypedTitle] = useState<string | null>(null);
  const title = typedTitle ?? (kind === "progress" ? "Six-monthly progress seminar" : SEMINAR_KIND_LABELS[kind]);
  const reviewsReport = kind === "progress"; // only a progress seminar reviews a report period
  const [startsAt, setStartsAt] = useState("");
  const [venue, setVenue] = useState("");
  const [reportDue, setReportDue] = useState("");
  const [year, setYear] = useState(new Date().getFullYear());
  const [period, setPeriod] = useState<Period>(new Date().getMonth() < 6 ? "January-June" : "July-December");
  const [scholarIds, setScholarIds] = useState<string[]>([]);
  const [panelIds, setPanelIds] = useState<string[]>([]);
  // Committee members put on the panel with the button: they may sit outside the list below.
  const [fromCommittees, setFromCommittees] = useState<{ id: string; name: string }[]>([]);
  const [committeeNote, setCommitteeNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!unitId && myUnits.length > 0 && myUnits[0]) setUnitId(myUnits[0].id);
  }, [myUnits, unitId]);
  useEffect(() => setScholarIds([]), [unitId]);

  async function addCommittees() {
    setCommitteeNote(null);
    try {
      const views = await Promise.all(scholarIds.map((sid) => api<CommitteeView>(`/scholars/${sid}/committee`)));
      const found = new Map<string, string>();
      for (const view of views) {
        for (const m of view.formations[0]?.members ?? []) if (m.faculty_id) found.set(m.faculty_id, m.name);
      }
      if (found.size === 0) {
        setCommitteeNote("None of these scholars has a committee member from this university.");
        return;
      }
      setPanelIds((ids) => [...new Set([...ids, ...found.keys()])]);
      setFromCommittees([...found].map(([id, name]) => ({ id, name })));
    } catch (err) {
      setCommitteeNote(errorText(err));
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const s = await api<SeminarDetail>("/seminars", {
        method: "POST",
        body: JSON.stringify({
          unit_id: unitId, kind, title, starts_at: new Date(startsAt).toISOString(), venue,
          ...(reviewsReport ? { report_due: reportDue, report_year: year, period } : {}),
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
      <PageHeader eyebrow="Seminars" title="Schedule a seminar" />
      <form className="clay card seminar-form" onSubmit={submit}>
        <Field label="Kind of seminar">
          <select value={kind} onChange={(e) => setKind(e.target.value as SeminarKind)}>
            {(Object.keys(SEMINAR_KIND_LABELS) as SeminarKind[]).map((k) => (
              <option key={k} value={k}>{SEMINAR_KIND_LABELS[k]}</option>
            ))}
          </select>
        </Field>
        <div className="two">
          <Field label="Department / unit">
            <select required value={unitId} onChange={(e) => setUnitId(e.target.value)}>
              {myUnits.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </Field>
          <Field label="Title">
            <input required maxLength={200} value={title} onChange={(e) => setTypedTitle(e.target.value)} />
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
        {reviewsReport && <div className="two">
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
        </div>}
        <PersonChecks<Scholar> legend="Scholars presenting" path={unitId ? `/scholars?unit_id=${unitId}` : null}
          value={scholarIds} onChange={setScholarIds} detail={(s) => s.roll_number} />
        <PersonChecks<Faculty> legend="Panel" path="/faculty" value={panelIds} onChange={setPanelIds}
          detail={(f) => f.unit.name} />
        <div className="committee-panel">
          <Button disabled={scholarIds.length === 0} onClick={addCommittees}>Add their advisory committee members to the panel</Button>
          {committeeNote && <p className="muted" role="status">{committeeNote}</p>}
          {fromCommittees.some((m) => panelIds.includes(m.id)) && (
            <ul className="plain-list" aria-label="On the panel from the committees">
              {fromCommittees.filter((m) => panelIds.includes(m.id)).map((m) => (
                <li key={m.id} className="row">
                  <span>{m.name} <span className="muted">· committee member, on the panel</span></span>
                  <Button kind="ghost" onClick={() => setPanelIds((ids) => ids.filter((x) => x !== m.id))}>Take off the panel</Button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="muted">Scholars, their supervisors, their advisory committees, the HoD/Dean and the panel will be notified. Committee members not on the panel are invited, not panellists.</p>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || scholarIds.length === 0}>
          {busy ? "Scheduling…" : "Schedule and notify"}
        </Button>
      </form>
    </>
  );
}

export default function ScheduleSeminarPage() {
  return <RequireRole roles={["unit_head", "admin"]}><ScheduleSeminarForm /></RequireRole>;
}
