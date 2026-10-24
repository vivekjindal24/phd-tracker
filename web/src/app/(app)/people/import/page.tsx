"use client";

import Link from "next/link";
import { useState } from "react";
import { Owl } from "@/components/brand/Owl";
import { DownloadButton } from "@/components/DownloadButton";
import { Button, Card, ErrorText, Field, PageHeader, Table } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { ImportKind, ImportReport, SettingsData } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "../new/people.css";
import "./import.css";

const KINDS: { kind: ImportKind; label: string; hint: string }[] = [
  { kind: "faculty", label: "1 · Faculty", hint: "Supervisors and other faculty, with their designation (it sets the UGC limit)." },
  { kind: "scholars", label: "2 · Scholars", hint: "Scholars name their supervisor by email, so import faculty first." },
  { kind: "history", label: "3 · Committee history", hint: "Past RDC/DRC decisions per roll number, so the register starts complete." },
];

function Summary({ report }: { report: ImportReport }) {
  const done = !report.dry_run;
  return (
    <dl className="import-summary">
      <div><dt>Rows read</dt><dd>{report.total_rows}</dd></div>
      <div><dt>{done ? "Created" : "Ready to create"}</dt><dd>{done ? report.created : report.to_create}</dd></div>
      <div><dt>Already in Anveshan</dt><dd>{report.already_present.length}</dd></div>
      <div className={report.errors.length ? "has-errors" : undefined}>
        <dt>Problems</dt><dd>{report.errors.length}</dd>
      </div>
    </dl>
  );
}

function Problems({ report }: { report: ImportReport }) {
  if (report.errors.length === 0) return null;
  return (
    <>
      <h2>Fix these rows, then upload the file again</h2>
      <p className="muted">Nothing has been saved. Row numbers are as shown in Excel.</p>
      <Table label="Problems in the file" head={["Row", "Column", "Problem"]}>
        {report.errors.map((e, i) => (
          <tr key={i}>
            <td className="mono">{e.row}</td>
            <td>{e.column}</td>
            <td>{e.message}</td>
          </tr>
        ))}
      </Table>
    </>
  );
}

export default function ImportPage() {
  const [kind, setKind] = useState<ImportKind>("faculty");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [invite, setInvite] = useState(true);
  const emailOn = useFetch<SettingsData>("/settings").data?.email_configured ?? false;
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function choose(next: ImportKind) {
    setKind(next);
    setFile(null);
    setReport(null);
  }

  async function send(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    const params = new URLSearchParams({
      dry_run: String(dryRun),
      send_invitations: String(!dryRun && emailOn && invite && kind !== "history"),
    });
    let body: ArrayBuffer;
    try {
      body = await file.arrayBuffer(); // a file edited after it was chosen can no longer be read
    } catch {
      setError(`“${file.name}” changed since you chose it. Choose the file again.`);
      setBusy(false);
      return;
    }
    try {
      setReport(await api<ImportReport>(`/import/${kind}?${params}`, { method: "POST", body }));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const checked = report?.dry_run === true;
  const canImport = checked && report.errors.length === 0 && report.to_create > 0;
  const hint = KINDS.find((k) => k.kind === kind)?.hint;

  return (
    <>
      <PageHeader eyebrow="Directory" title="Import from Excel" />
      <div className="import-grid">
        <Card className="import-steps">
          <fieldset className="kind-picker import-kinds">
            <legend className="visually-hidden">What to import</legend>
            {KINDS.map((k) => (
              <label key={k.kind} className={kind === k.kind ? "chosen" : undefined}>
                <input type="radio" name="kind" checked={kind === k.kind} onChange={() => choose(k.kind)} />
                {k.label}
              </label>
            ))}
          </fieldset>
          <p className="muted">{hint}</p>
          <div className="row">
            <DownloadButton path={`/import/${kind}/template`} from="api">Download template</DownloadButton>
          </div>
          <Field label="Filled-in file" hint="Excel (.xlsx) or CSV, up to 2,000 rows. Only the first sheet is read.">
            <input type="file" accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onClick={(e) => { e.currentTarget.value = ""; }} /* re-choosing the same, edited file must fire onChange */
              onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setError(null); }} />
          </Field>
          <Button kind={canImport ? "secondary" : "primary"} disabled={!file || busy} onClick={() => send(true)}>
            {busy && !checked ? "Checking…" : "Check file"}
          </Button>
          <ErrorText>{error}</ErrorText>
        </Card>

        <div className="import-result">
          {!report && (
            <Card className="import-empty">
              <Owl pose="reading" size={96} />
              <p>Check a file first — nothing is saved until you press <strong>Import</strong>, and only when every row is right.</p>
            </Card>
          )}
          {report && (
            <Card>
              <Summary report={report} />
              <Problems report={report} />
              {canImport && (
                <div className="import-go">
                  {kind !== "history" && (emailOn ? (
                    <label className="check">
                      <input type="checkbox" checked={invite} onChange={(e) => setInvite(e.target.checked)} />
                      Email each new person a link to set their password
                    </label>
                  ) : (
                    <p className="muted">Email isn&apos;t set up on this server, so no set-password links go out. Send them from each profile once it is.</p>
                  ))}
                  <Button kind="primary" disabled={busy} onClick={() => send(false)}>
                    {busy ? "Importing…" : `Import ${report.to_create} ${report.to_create === 1 ? "row" : "rows"}`}
                  </Button>
                </div>
              )}
              {checked && report.errors.length === 0 && report.to_create === 0 && (
                <p className="muted">Everything in this file is already in Anveshan.</p>
              )}
              {!report.dry_run && (
                <div className="import-done" role="status">
                  <h2>Imported</h2>
                  {report.invitations_sent !== null && (
                    <p>{report.invitations_sent} invitation{report.invitations_sent === 1 ? "" : "s"} sent.</p>
                  )}
                  {report.invitations_failed.length > 0 && (
                    <ErrorText>
                      Invitations could not be sent to: {report.invitations_failed.join(", ")}. Send them again from each profile.
                    </ErrorText>
                  )}
                  <Link href={kind === "faculty" ? "/faculty" : kind === "scholars" ? "/scholars" : "/register"}>
                    See them →
                  </Link>
                </div>
              )}
              {report.already_present.length > 0 && (
                <details className="import-skipped">
                  <summary>{report.already_present.length} rows already in Anveshan — skipped</summary>
                  <ul>
                    {report.already_present.map((s) => (
                      <li key={s.row}>Row {s.row}: {s.what}</li>
                    ))}
                  </ul>
                </details>
              )}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
