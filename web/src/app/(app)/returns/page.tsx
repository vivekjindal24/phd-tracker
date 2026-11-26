"use client";

import Link from "next/link";
import { useState } from "react";
import { DownloadButton } from "@/components/DownloadButton";
import { Card, Field, PageHeader } from "@/components/ui/kit";
import { NotForYourRole } from "@/components/ui/RequireRole";
import { useSession } from "@/lib/session";

const NIRF = [
  ["nirf-phd", "Ph.D. student details", "Pursuing at the end of the year, and graduated in each of the last three, full time and part time."],
  ["nirf-sponsored", "Sponsored research details", "Each of the last three financial years: projects that received money, their funding agencies, the amount received and in words."],
  ["nirf-patents", "Patents (IPR)", "Verified patents published and granted in each of the last three calendar years."],
] as const;
const AISHE = [
  ["aishe-enrolment", "Ph.D. student enrolment", "Scholars on the rolls in the year, by department and year of study: category by gender, with PwBD and minorities out of the total."],
  ["aishe-foreign", "Foreign students", "NRIs, PIOs and other foreign nationals on the rolls, by department and country."],
  ["aishe-results", "Examination results", "Scholars whose viva was held in the year, and those awarded the degree, split as enrolment is."],
] as const;
const YEARS_SHOWN = 12;

const label = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, "0")}`;

export default function ReturnsPage() {
  const { me } = useSession();
  const now = new Date();
  const current = now.getMonth() >= 6 ? now.getFullYear() : now.getFullYear() - 1;
  // NIRF and AISHE ask about the year just finished.
  const [year, setYear] = useState(current - 1);

  if (!me?.roles.some((r) => r === "research_office" || r === "vice_chancellor")) return <NotForYourRole />;
  const list = (sheets: typeof NIRF | typeof AISHE) => (
    <ul className="plain-list">
      {sheets.map(([key, title, what]) => (
        <li key={key} className="row">
          <span><strong>{title}</strong><br /><span className="muted">{what}</span></span>
          <DownloadButton path={`/returns/${key}.csv?year=${year}`}>Download CSV</DownloadButton>
        </li>
      ))}
    </ul>
  );

  return (
    <>
      <PageHeader eyebrow="Government returns" title="NIRF and AISHE: research degrees" />
      <div className="toolbar">
        <Field label="Academic year">
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {Array.from({ length: YEARS_SHOWN }, (_, i) => current - i).map((y) => <option key={y} value={y}>{label(y)}</option>)}
          </select>
        </Field>
      </div>
      <Card>
        <h2>NIRF</h2>
        <p className="muted">The Ph.D., sponsored research and patent tables of the NIRF data form. NIRF takes publications from Scopus and Web of Science itself.</p>
        {list(NIRF)}
      </Card>
      <Card>
        <h2>AISHE</h2>
        <p className="muted">
          The Ph.D. rows of the AISHE university form. Set each department&apos;s AISHE discipline in Settings → University structure. A
          scholar whose category or gender is not recorded is counted in a column of its own, and one with no admission date is left out
          and named at the end, so their profiles can be completed before filing. The approved intake (seats) is not kept here: enter it
          in AISHE directly.
        </p>
        {list(AISHE)}
      </Card>
      <Card>
        <h2>How the counts are made</h2>
        <p className="muted">
          The forms do not say how to count these, so Anveshan uses these rules. Check them against how your office has filed before,
          and tell your administrator if a rule differs.
        </p>
        <ul>
          <li>NIRF Ph.D. pursuing: admitted by 30 June and neither awarded nor left by then.</li>
          <li>AISHE enrolment: on the rolls at any time in the academic year, so a scholar awarded mid-year is counted.</li>
          <li>AISHE results: &ldquo;appeared&rdquo; means the viva was held in the year; &ldquo;awarded&rdquo; means the degree was awarded in it.</li>
          <li>NIRF sponsored research: projects that received money in the financial year (April to March).</li>
          <li>Patents: verified patents only, by calendar year.</li>
        </ul>
      </Card>
      <p className="muted">The NAAC Criterion 3 rows are on <Link href="/naac">NAAC data</Link>.</p>
    </>
  );
}
