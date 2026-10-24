"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import type { Me } from "@/lib/types";
import "./nav.css";

type Item = { href: string; label: string; show: (me: Me) => boolean };
type Group = { label: string; items: Item[] };
type Entry = Item | Group;

const notOnlyOffice = (me: Me) => me.roles.some((r) => r !== "exam_office" && r !== "library");
const onlyScholar = (me: Me) => me.roles.length === 1 && me.roles[0] === "scholar";

// Grouped navigation (DESIGN_SYSTEM.md §4). Only pages that exist are listed.
const NAV: Entry[] = [
  { href: "/home", label: "Home", show: () => true },
  {
    label: "Work",
    items: [
      { href: "/queue", label: "My queue", show: (me) => !onlyScholar(me) },
      { href: "/reports", label: "Progress reports", show: notOnlyOffice },
      { href: "/meetings", label: "Meetings", show: notOnlyOffice },
      { href: "/seminars", label: "Seminars", show: (me) => notOnlyOffice(me) || me.faculty_id !== null },
      { href: "/todos", label: "My to-dos", show: (me) => me.scholar_id !== null },
      { href: "/coursework", label: "Coursework", show: (me) => me.modules.coursework && !me.roles.every((r) => r === "library") },
    ],
  },
  {
    label: "Research",
    items: [
      { href: "/publications", label: "Publications", show: (me) => me.modules.publications && !me.roles.every((r) => r === "exam_office") },
      { href: "/conferences", label: "Conferences & talks", show: (me) => me.modules.conferences && !me.roles.every((r) => r === "exam_office") },
      { href: "/documents", label: "Drafts & chapters", show: (me) => me.modules.documents && (me.scholar_id !== null || me.roles.includes("supervisor")) },
      { href: "/thesis", label: "Thesis", show: (me) => me.modules.documents },
    ],
  },
  {
    label: "People",
    items: [
      { href: "/scholars", label: "Scholars", show: (me) => !onlyScholar(me) },
      { href: "/scholars", label: "My profile", show: onlyScholar }, // redirects to own profile
      { href: "/faculty", label: "Faculty", show: () => true },
      { href: "/admissions", label: "Admissions", show: (me) => me.modules.admissions && me.roles.some((r) => r === "admin" || r === "unit_head" || r === "research_office") },
    ],
  },
  {
    label: "Grants",
    items: [
      { href: "/fellowships", label: "Fellowships", show: (me) => me.modules.fellowships && notOnlyOffice(me) },
      { href: "/projects", label: "Research projects", show: (me) => me.modules.projects && (me.faculty_id !== null || notOnlyOffice(me)) },
    ],
  },
  { href: "/leadership", label: "Leadership", show: (me) => me.roles.some((r) => r === "unit_head" || r === "admin" || r === "research_office") },
  { href: "/register", label: "Register", show: (me) => me.roles.some((r) => r !== "library") },
  { href: "/settings", label: "Settings", show: (me) => me.is_root_admin },
];

const isGroup = (e: Entry): e is Group => "items" in e;

export function Nav({ me }: { me: Me }) {
  const pathname = usePathname();
  const navRef = useRef<HTMLElement>(null);
  const active = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  // Close open menus on navigation and on clicks outside.
  useEffect(() => {
    navRef.current?.querySelectorAll("details[open]").forEach((d) => d.removeAttribute("open"));
  }, [pathname]);
  useEffect(() => {
    const close = (e: MouseEvent) => {
      navRef.current?.querySelectorAll("details[open]").forEach((d) => {
        if (!d.contains(e.target as Node)) d.removeAttribute("open");
      });
    };
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, []);

  return (
    <nav className="nav" aria-label="Main navigation" ref={navRef}>
      {NAV.map((entry) => {
        if (!isGroup(entry)) {
          return entry.show(me) ? (
            <Link key={entry.label} href={entry.href} aria-current={active(entry.href) ? "page" : undefined}>
              {entry.label}
            </Link>
          ) : null;
        }
        const visible = entry.items.filter((i) => i.show(me));
        if (visible.length === 0) return null;
        const groupActive = visible.some((i) => active(i.href));
        return (
          <details key={entry.label} className="nav-group">
            <summary className={groupActive ? "nav-group-active" : undefined}>{entry.label}</summary>
            <div className="nav-menu clay">
              {visible.map((i) => (
                <Link key={i.label} href={i.href} aria-current={active(i.href) ? "page" : undefined}>
                  {i.label}
                </Link>
              ))}
            </div>
          </details>
        );
      })}
    </nav>
  );
}
