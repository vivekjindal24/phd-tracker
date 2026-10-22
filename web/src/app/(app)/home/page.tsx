"use client";

import Link from "next/link";
import { Owl } from "@/components/brand/Owl";
import { Card, PageHeader } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import { ROLE_LABELS } from "@/lib/types";
import "./home.css";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function HomePage() {
  const { me } = useSession();
  if (!me) return null;
  const firstName = me.full_name.replace(/^(Dr\.|Prof\.)\s+/, "").split(" ")[0];

  return (
    <>
      <section className="home-hero">
        <div>
          <PageHeader eyebrow={`${greeting()}, ${firstName}`} title="Welcome to Anveshan" />
          <ul className="role-chips" aria-label="Your roles">
            {me.unit_roles.map((r) => (
              <li key={`${r.role}-${r.unit_id}`} className="badge">
                {r.role === "unit_head" ? "Head" : ROLE_LABELS[r.role]} · {r.unit_name}
              </li>
            ))}
            {me.roles
              .filter((role) => role !== "unit_head" && role !== "admin")
              .map((role) => (
                <li key={role} className="badge">
                  {ROLE_LABELS[role]}
                </li>
              ))}
          </ul>
        </div>
        <Owl pose="idle" size={180} />
      </section>

      <div className="home-grid">
        <Card className="empty-state">
          <Owl pose="empty" size={96} />
          <h2>Your dashboard fills up as work arrives</h2>
          <p>Meetings, progress reports and approvals waiting for you will show up here.</p>
        </Card>
        {me.is_root_admin && (
          <Card>
            <h2>Set up your university</h2>
            <p className="muted">
              Build the faculty and department tree, choose which modules to switch on, and
              review the approval chains.
            </p>
            <Link href="/settings" className="btn btn-primary">
              Open settings
            </Link>
          </Card>
        )}
      </div>
    </>
  );
}
