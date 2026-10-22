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

type DueStatus = "upcoming" | "due_soon" | "overdue" | "submitted";
type Overdue = { scholar: Ref; seminar: Ref; report_due: string };
type UnitSection = {
  unit_id: string;
  unit_name: string;
  roles: ("unit_head" | "admin")[];
  scholars_by_stage: Record<string, number>;
  total_scholars: number;
  overdue_reports: Overdue[];
  stuck_items: { item_type: string; id: string; title: string; scholar: string; step: string; days: number }[];
  supervisor_load: { name: string; load: number; max: number }[];
  children: { id: string; name: string; scholars: number; overdue: number }[];
  without_supervisor?: Ref[];
  units_without_head?: Ref[];
};
type Dashboard = {
  queue_count: number;
  queue_oldest_days: number | null;
  queue: { item_type: string; id: string; label: string; title: string; scholar: Ref; step: string; days_waiting: number }[];
  upcoming_seminars: { id: string; title: string; starts_at: string; report_due: string; unit: string }[];
  scholar?: {
    stage: string;
    supervisor: string | null;
    next_seminar: { id: string; title: string; starts_at: string; venue: string; report_due: string; due_status: DueStatus } | null;
    in_progress: { item_type: string; id: string; title: string; state: ItemState; waiting_on: string | null }[];
    open_todos: number;
    last_meeting: string | null;
    next_meeting: string | null;
    latest_decision: { milestone_type: MilestoneType; status: string; resolution_number: string | null } | null;
  };
  supervisor?: { load: number; max_scholars: number; scholars: { id: string; name: string; stage: string }[]; overdue_reports: Overdue[] };
  units: UnitSection[];
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
      <h2 id={`unit-${u.unit_id}`}>{u.unit_name} <span className="badge">{roleText}</span></h2>
      <div className="bento">
        <Tile label="Scholars" value={u.total_scholars} href="/scholars" tone="tile-accent" />
        <Tile label="Overdue reports" value={u.overdue_reports.length} tone={u.overdue_reports.length ? "tile-coral" : "tile-sage"} />
        <Tile label="Stuck over 14 days" value={u.stuck_items.length} tone={u.stuck_items.length ? "tile-butter" : ""} />
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
                <li key={c.id}><strong>{c.name}</strong> <span className="muted">· {c.scholars} scholars</span>
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

export default function HomePage() {
  const { me } = useSession();
  const { data: d, error } = useFetch<Dashboard>("/dashboard");
  if (!me) return null;
  const firstName = me.full_name.replace(/^(Dr\.|Prof\.)\s+/, "").split(" ")[0];
  const sch = d?.scholar;

  return (
    <>
      <section className="home-hero">
        <div>
          <div className="eyebrow">{greeting()}, {firstName}</div>
          <h1>
            {d && d.queue_count > 0
              ? `${d.queue_count} item${d.queue_count === 1 ? " is" : "s are"} waiting for you`
              : sch?.next_seminar ? "Your next seminar is coming up" : "Welcome back"}
          </h1>
        </div>
        <Owl pose={d && d.queue_count === 0 ? "idle" : "reading"} size={150} />
      </section>
      <ErrorText>{error}</ErrorText>
      {d && (
        <>
          {(d.queue_count > 0 || !sch) && (
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
              <h2 id="dash-sup">Your scholars <span className="badge">{d.supervisor.load}/{d.supervisor.max_scholars} (UGC limit)</span></h2>
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
                    <span className="muted"> · {s.unit} · report due {formatDate(s.report_due)}</span></li>
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
