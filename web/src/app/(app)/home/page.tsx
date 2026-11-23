"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Owl } from "@/components/brand/Owl";
import { StateBadge } from "@/components/items/StateBadge";
import { Card, ErrorText } from "@/components/ui/kit";
import { formatDate, formatWhen } from "@/lib/format";
import { useSession } from "@/lib/session";
import { MILESTONE_LABELS, ROLE_LABELS, STAGES } from "@/lib/types";
import type { ItemState, MilestoneType, Ref } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./home.css";
import { NoticeBoardCard } from "@/components/NoticeBoardCard";

type DueStatus = "upcoming" | "due_soon" | "overdue" | "submitted";
type Overdue = { scholar: Ref; seminar: Ref; report_due: string };
type UnitSection = {
  unit_id: string;
  unit_name: string;
  roles: ("unit_head" | "admin" | "vice_chancellor")[];
  scholars_by_stage: Record<string, number>;
  total_scholars: number;
  overdue_reports: Overdue[];
  stuck_items: { item_type: string; id: string; title: string; scholar: string; step: string; days: number }[];
  supervisor_load: { name: string; load: number; max: number }[];
  children: { id: string; name: string; scholars: number; overdue: number }[];
  publications_this_year: number | null;
  faculty_publications_this_year: number | null;
  without_supervisor?: Ref[];
  units_without_head?: Ref[];
};
type Dashboard = {
  queue_count: number;
  queue_oldest_days: number | null;
  queue: { item_type: string; id: string; label: string; title: string; scholar: Ref; step: string; days_waiting: number }[];
  upcoming_seminars: { id: string; title: string; starts_at: string; report_due: string | null; unit: string }[];
  scholar?: {
    stage: string;
    supervisor: string | null;
    next_seminar: { id: string; title: string; starts_at: string; venue: string; report_due: string; due_status: DueStatus } | null;
    in_progress: { item_type: string; id: string; title: string; state: ItemState; waiting_on: string | null }[];
    open_todos: number;
    approved_publications: number | null;
    fellowship_ends: string | null;
    coursework: { credits: number; min_credits: number; cgpa: number | null; cleared_on: string | null } | null;
    profile_incomplete: boolean;
    duration: { limit_date: string | null; days_left: number | null; status: string; warnings: string[] };
    last_meeting: string | null;
    next_meeting: string | null;
    latest_decision: { milestone_type: MilestoneType; status: string; resolution_number: string | null } | null;
  };
  supervisor?: { load: number; max_scholars: number; scholars: { id: string; name: string; stage: string }[]; overdue_reports: Overdue[] };
  units: UnitSection[];
  // Absent for someone with no grievance role and no scholar record (grievances.home).
  grievances: { decides: boolean; to_decide: number; overdue: number; next_due: string | null; to_answer: number; past_deadline?: number } | null;
  // Null unless the Library or a member of faculty, with publications on (faculty_papers.home).
  faculty_papers: { to_verify: number; returned: number } | null;
  // Null unless the verifying office, a member of faculty or a scholar, with patents on.
  patents: { checks: boolean; to_verify: number; returned: number } | null;
};

const DUE_TEXT: Record<DueStatus, [string, string]> = {
  upcoming: ["Report due", "badge"],
  due_soon: ["Report due soon", "badge badge-draft"],
  overdue: ["Report overdue", "badge badge-sent_back"],
  submitted: ["Report submitted", "badge badge-approved"],
};

function greeting(): string {
  const hour = new Date().getHours();
  return hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
}

function Tile({ label, value, href, tone, children }: { label: string; value?: ReactNode; href?: string; tone?: string; children?: ReactNode }) {
  const body = (
    <>
      {value !== undefined && <span className="tile-num">{value}</span>}
      <span className="tile-label">{label}</span>
      {children}
    </>
  );
  return href ? (
    <Link href={href} className={`clay tile ${tone ?? ""}`}>{body}</Link>
  ) : (
    <div className={`clay tile ${tone ?? ""}`}>{body}</div>
  );
}

function OverdueList({ rows }: { rows: Overdue[] }) {
  if (rows.length === 0) return <p className="muted">No overdue reports. 🎉</p>;
  return (
    <ul className="plain-list">
      {rows.map((o) => (
        <li key={`${o.scholar.id}-${o.seminar.id}`}>
          <Link href={`/scholars/${o.scholar.id}`}>{o.scholar.name}</Link>
          <span className="muted"> · due {formatDate(o.report_due)} for {o.seminar.name}</span>
        </li>
      ))}
    </ul>
  );
}

function StageBars({ counts }: { counts: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(counts));
  return (
    <ul className="stage-bars" aria-label="Scholars by stage">
      {STAGES.map((s) => (
        <li key={s}>
          <span className="stage-name">{s}</span>
          <span className="stage-track"><span className="stage-fill" style={{ width: `${((counts[s] ?? 0) / max) * 100}%` }} /></span>
          <span className="stage-count">{counts[s] ?? 0}</span>
        </li>
      ))}
    </ul>
  );
}

function UnitBlock({ u }: { u: UnitSection }) {
  const roleText = u.roles.map((r) => (r === "unit_head" ? "Head" : ROLE_LABELS[r])).join(" & ");
  return (
    <section className="dash-section" aria-labelledby={`unit-${u.unit_id}`}>
      <h2 id={`unit-${u.unit_id}`}>{u.unit_name} <span className="badge">{roleText}</span>{" "}
        <Link className="dash-more" href={`/leadership?unit=${u.unit_id}`}>Leadership view →</Link></h2>
      <div className="bento">
        <Tile label="Scholars" value={u.total_scholars} href="/scholars" tone="tile-accent" />
        <Tile label="Overdue reports" value={u.overdue_reports.length} tone={u.overdue_reports.length ? "tile-coral" : "tile-sage"} />
        <Tile label="Stuck over 14 days" value={u.stuck_items.length} tone={u.stuck_items.length ? "tile-butter" : ""} />
        {u.publications_this_year !== null && (
          <Tile label="Publications this year" value={u.publications_this_year} href="/publications" tone="tile-sage" />
        )}
        {u.faculty_publications_this_year !== null && (
          <Tile label="Faculty publications this year" value={u.faculty_publications_this_year} href="/faculty-publications?verification=verified" tone="tile-sage" />
        )}
      </div>
      <div className="dash-grid">
        <Card><h3>By stage</h3><StageBars counts={u.scholars_by_stage} /></Card>
        <Card><h3>Overdue reports</h3><OverdueList rows={u.overdue_reports} /></Card>
        {u.stuck_items.length > 0 && (
          <Card>
            <h3>Stuck in the chain</h3>
            <ul className="plain-list">
              {u.stuck_items.map((s) => (
                <li key={s.id}><Link href={`/items/${s.item_type}/${s.id}`}>{s.scholar} · {s.title}</Link>
                  <span className="muted"> · at {s.step} for {s.days} days</span></li>
              ))}
            </ul>
          </Card>
        )}
        <Card>
          <h3>Supervisor load</h3>
          <ul className="plain-list">
            {u.supervisor_load.map((s) => (
              <li key={s.name} className="load-row">
                <span>{s.name}</span>
                <span className={`meter${s.load >= s.max ? " meter-full" : ""}`}>
                  <span className="meter-track"><span className="meter-fill" style={{ width: `${s.max ? Math.min(100, (s.load / s.max) * 100) : 100}%` }} /></span>
                  {s.load}/{s.max}
                </span>
              </li>
            ))}
          </ul>
        </Card>
        {u.children.length > 0 && (
          <Card>
            <h3>By unit</h3>
            <ul className="plain-list">
              {u.children.map((c) => (
                <li key={c.id}><strong>{c.name}</strong> <span className="muted">· {c.scholars} {c.scholars === 1 ? "scholar" : "scholars"}</span>
                  {c.overdue > 0 && <span className="badge badge-sent_back" style={{ marginLeft: 8 }}>{c.overdue} overdue</span>}</li>
              ))}
            </ul>
          </Card>
        )}
        {u.without_supervisor && (u.without_supervisor.length > 0 || (u.units_without_head ?? []).length > 0) && (
          <Card>
            <h3>Setup gaps</h3>
            {u.without_supervisor.length > 0 && (<><p className="muted">Scholars without a supervisor</p>
              <ul className="plain-list">{u.without_supervisor.map((s) => <li key={s.id}><Link href={`/scholars/${s.id}`}>{s.name}</Link></li>)}</ul></>)}
            {(u.units_without_head ?? []).length > 0 && (<><p className="muted">Units without a head</p>
              <ul className="plain-list">{u.units_without_head!.map((x) => <li key={x.id}>{x.name}</li>)}</ul></>)}
          </Card>
        )}
      </div>
    </section>
  );
}

/** What waits on a grievance decider, and for the Vice Chancellor what is past its deadline. */
function GrievanceTiles({ g }: { g: NonNullable<Dashboard["grievances"]> }) {
  const late = g.past_deadline ?? 0;
  if (!g.decides && late === 0) return null;
  const sub = g.overdue > 0 ? `${g.overdue} past the deadline` : g.next_due ? `next due ${formatDate(g.next_due)}` : null;
  return (
    <section className="dash-section" aria-label="Grievances">
      <div className="bento">
        {g.decides && (
          <Tile label="Grievances to decide" value={g.to_decide} href="/grievances"
            tone={g.overdue ? "tile-coral" : g.to_decide ? "tile-accent" : "tile-sage"}>
            {sub && <span className="tile-sub">{sub}</span>}
          </Tile>
        )}
        {late > 0 && (
          <Tile label="Grievances past their deadline" value={late} href="/grievances" tone="tile-coral">
            <span className="tile-sub">university-wide</span>
          </Tile>
        )}
      </div>
    </section>
  );
}

/** The Library's faculty papers to verify, and a member of faculty's papers it returned. */
function FacultyPaperTiles({ f, isLibrary }: { f: NonNullable<Dashboard["faculty_papers"]>; isLibrary: boolean }) {
  if (!isLibrary && f.returned === 0) return null;
  return (
    <section className="dash-section" aria-label="Faculty publications">
      <div className="bento">
        {isLibrary && (
          <Tile label="Faculty papers to verify" value={f.to_verify} href="/faculty-publications?verification=waiting"
            tone={f.to_verify ? "tile-accent" : "tile-sage"} />
        )}
        {f.returned > 0 && (
          <Tile label="Your papers returned by the Library" value={f.returned}
            href="/faculty-publications?verification=returned" tone="tile-butter">
            <span className="tile-sub">correct them to send them back</span>
          </Tile>
        )}
      </div>
    </section>
  );
}

/** The verifying office's patents to check, and an inventor's patents it returned. */
function PatentTiles({ p }: { p: NonNullable<Dashboard["patents"]> }) {
  if (!p.checks && p.returned === 0) return null;
  return (
    <section className="dash-section" aria-label="Patents">
      <div className="bento">
        {p.checks && (
          <Tile label="Patents to verify" value={p.to_verify} href="/patents?verification=waiting"
            tone={p.to_verify ? "tile-accent" : "tile-sage"} />
        )}
        {p.returned > 0 && (
          <Tile label="Your patents returned for a correction" value={p.returned}
            href="/patents?verification=returned" tone="tile-butter">
            <span className="tile-sub">correct them to send them back</span>
          </Tile>
        )}
      </div>
    </section>
  );
}

const GRIEVANCE_ROLES = new Set(["grievance_cell", "ombudsperson"]);

// "Prof. Kavita Rao" -> "Kavita"; "Justice (Retd.) S. K. Menon" -> "S. K. Menon": titles go, and
// a name starting with initials keeps the surname rather than greeting an initial.
const HONORIFIC = /^(?:(?:dr|prof|mr|mrs|ms|shri|smt|kumari|justice)\.?|\(retd\.?\))\s+/i;
function greetingName(full: string): string {
  let name = full.trim();
  while (HONORIFIC.test(name)) name = name.replace(HONORIFIC, "");
  const first = name.split(" ")[0] ?? name;
  return /^[A-Z]\.$/.test(first) ? name : first;
}

export default function HomePage() {
  const { me } = useSession();
  const { data: d, error } = useFetch<Dashboard>("/dashboard");
  if (!me) return null;
  const firstName = greetingName(me.full_name);
  const sch = d?.scholar;
  // Someone who only handles grievances has no approval queue to show.
  const grievanceOnly = !me.is_root_admin && me.roles.every((r) => GRIEVANCE_ROLES.has(r));
  const toDecide = d?.grievances?.decides ? d.grievances.to_decide : 0;
  const isLibrary = me.roles.includes("library");
  const toVerify = (isLibrary ? (d?.faculty_papers?.to_verify ?? 0) : 0) + (d?.patents?.checks ? d.patents.to_verify : 0);

  return (
    <>
      <section className="home-hero">
        <div>
          <div className="eyebrow">{greeting()}, {firstName}</div>
          <h1>
            {d && d.queue_count > 0
              ? `${d.queue_count} item${d.queue_count === 1 ? " is" : "s are"} waiting for you`
              : toDecide > 0 ? `${toDecide} grievance${toDecide === 1 ? " is" : "s are"} waiting for you`
              : toVerify > 0 ? `${toVerify} record${toVerify === 1 ? " is" : "s are"} waiting for you to verify`
              : sch?.next_seminar ? "Your next seminar is coming up" : "Welcome back"}
          </h1>
        </div>
        <Owl pose={d && d.queue_count === 0 && toDecide === 0 && toVerify === 0 ? "idle" : "reading"} size={150} />
      </section>
      <ErrorText>{error}</ErrorText>
      <NoticeBoardCard />
      {d && (
        <>
          {d.grievances && <GrievanceTiles g={d.grievances} />}
          {d.faculty_papers && <FacultyPaperTiles f={d.faculty_papers} isLibrary={isLibrary} />}
          {d.patents && <PatentTiles p={d.patents} />}
          {(d.queue_count > 0 || (!sch && !grievanceOnly)) && (
            <section className="dash-section">
              <div className="bento">
                <Tile label="Waiting for your decision" value={d.queue_count} href="/queue" tone={d.queue_count ? "tile-accent" : "tile-sage"}>
                  {d.queue_oldest_days ? <span className="tile-sub">oldest {d.queue_oldest_days} days</span> : null}
                </Tile>
                {d.queue.slice(0, 3).map((q) => (
                  <Tile key={q.id} label={`${q.scholar.name} · ${q.step}`} href={`/items/${q.item_type}/${q.id}`}>
                    <span className="tile-title">{q.label} · {q.title}</span>
                  </Tile>
                ))}
              </div>
            </section>
          )}

          {sch && (
            <section className="dash-section" aria-label="Your research">
              <div className="bento">
                {(d.grievances?.to_answer ?? 0) > 0 && (
                  <Tile label="Your grievance has a decision" href="/grievances" tone="tile-butter tile-wide">
                    <span>Accept it, or appeal within 15 days of the decision.</span>
                  </Tile>
                )}
                {sch.profile_incomplete && (
                  <Tile label="Complete your profile" href={`/scholars/${me.scholar_id}`} tone="tile-wide">
                    <span>A few details about you are not on record yet. It takes a minute.</span>
                  </Tile>
                )}
                {sch.next_seminar ? (
                  <Tile label={sch.next_seminar.title} href={`/seminars/${sch.next_seminar.id}`} tone="tile-accent tile-wide">
                    <span className="tile-num tile-num-sm">{formatWhen(sch.next_seminar.starts_at)}</span>
                    <span className={DUE_TEXT[sch.next_seminar.due_status][1]}>
                      {DUE_TEXT[sch.next_seminar.due_status][0]} · {formatDate(sch.next_seminar.report_due)}
                    </span>
                  </Tile>
                ) : <Tile label="No seminar scheduled yet" value="—" />}
                <Tile label="Open to-dos" value={sch.open_todos} href="/todos" tone={sch.open_todos ? "tile-butter" : "tile-sage"} />
                <Tile label="Stage" value={sch.stage} tone="tile-text" />
                {(sch.duration.status === "near" || sch.duration.status === "over") && sch.duration.limit_date && (
                  <Tile label={sch.duration.status === "over" ? "Past the maximum duration" : "Days left to submit"}
                    value={sch.duration.status === "over" ? formatDate(sch.duration.limit_date) : (sch.duration.days_left ?? 0)}
                    href={`/scholars/${me?.scholar_id}`} tone="tile-coral" />
                )}
                {sch.coursework && (
                  <Tile label={sch.coursework.cleared_on ? `Coursework cleared ${formatDate(sch.coursework.cleared_on)}` : `Coursework credits (of ${sch.coursework.min_credits})`}
                    value={sch.coursework.credits} href="/coursework"
                    tone={sch.coursework.cleared_on || sch.coursework.credits >= sch.coursework.min_credits ? "tile-sage" : "tile-butter"} />
                )}
                {sch.fellowship_ends && (
                  <Tile label="Fellowship ends" value={formatDate(sch.fellowship_ends)} href="/fellowships" tone="tile-butter" />
                )}
                {sch.approved_publications !== null && (
                  <Tile label="Verified publications" value={sch.approved_publications} href="/publications" tone="tile-sage" />
                )}
                <Tile label={sch.next_meeting ? `Next meeting ${formatDate(sch.next_meeting)}` : "Last meeting"}
                  value={sch.last_meeting ? formatDate(sch.last_meeting) : "—"} href="/meetings" tone="tile-text" />
              </div>
              <div className="dash-grid">
                <Card>
                  <h3>In progress</h3>
                  {sch.in_progress.length === 0 ? <p className="muted">Nothing in progress.</p> : (
                    <ul className="plain-list">
                      {sch.in_progress.map((i) => (
                        <li key={i.id}><Link href={`/items/${i.item_type}/${i.id}`}>{i.title.replace("-", "–")}</Link>{" "}
                          <StateBadge state={i.state} waitingOn={i.waiting_on} /></li>
                      ))}
                    </ul>
                  )}
                  <Link href="/reports/new" className="btn" style={{ marginTop: "var(--space-3)" }}>New report</Link>
                </Card>
                <Card>
                  <h3>Latest committee decision</h3>
                  {sch.latest_decision ? (
                    <p>{MILESTONE_LABELS[sch.latest_decision.milestone_type]} · {sch.latest_decision.status}
                      {sch.latest_decision.resolution_number && <span className="muted"> · {sch.latest_decision.resolution_number}</span>}</p>
                  ) : <p className="muted">None recorded yet.</p>}
                  {sch.supervisor && <p className="muted">Supervisor: {sch.supervisor}</p>}
                </Card>
              </div>
            </section>
          )}

          {d.supervisor && (
            <section className="dash-section" aria-labelledby="dash-sup">
              <h2 id="dash-sup">Your scholars <span className="badge">{d.supervisor.load}/{d.supervisor.max_scholars} limit</span></h2>
              <div className="dash-grid">
                <Card>
                  <ul className="plain-list">
                    {d.supervisor.scholars.map((s) => (
                      <li key={s.id}><Link href={`/scholars/${s.id}`}>{s.name}</Link> <span className="badge">{s.stage}</span></li>
                    ))}
                    {d.supervisor.scholars.length === 0 && <li className="muted">No scholars assigned yet.</li>}
                  </ul>
                </Card>
                <Card><h3>Overdue reports</h3><OverdueList rows={d.supervisor.overdue_reports} /></Card>
              </div>
            </section>
          )}

          {d.units.map((u) => <UnitBlock key={u.unit_id} u={u} />)}

          {d.upcoming_seminars.length > 0 && (
            <section className="dash-section" aria-labelledby="dash-sem">
              <h2 id="dash-sem">Upcoming seminars</h2>
              <ul className="plain-list">
                {d.upcoming_seminars.map((s) => (
                  <li key={s.id}><Link href={`/seminars/${s.id}`}>{formatWhen(s.starts_at)} · {s.title}</Link>
                    <span className="muted"> · {s.unit}{s.report_due && ` · report due ${formatDate(s.report_due)}`}</span></li>
                ))}
              </ul>
            </section>
          )}

          {me.is_root_admin && (
            <Card>
              <h3>Set up your university</h3>
              <p className="muted">Build the structure, switch modules on and review approval chains.</p>
              <Link href="/settings" className="btn btn-primary">Open settings</Link>
            </Card>
          )}
        </>
      )}
    </>
  );
}
