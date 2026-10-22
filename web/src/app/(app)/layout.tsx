"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, ErrorText } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import type { Me } from "@/lib/types";
import "./shell.css";

type NavItem = { href: string; label: string; show: (me: Me) => boolean };

// Only pages that exist are listed; groups grow with each phase (UX Flow 0).
const NAV: NavItem[] = [
  { href: "/home", label: "Home", show: () => true },
  {
    href: "/scholars",
    label: "Scholars",
    show: (me) => me.roles.some((r) => r !== "scholar"),
  },
  {
    href: "/scholars", // redirects a scholar to their own profile
    label: "My profile",
    show: (me) => me.roles.length === 1 && me.roles[0] === "scholar",
  },
  {
    href: "/meetings",
    label: "Meetings",
    show: (me) => me.roles.some((r) => r !== "exam_office" && r !== "library"),
  },
  {
    href: "/reports",
    label: "Reports",
    show: (me) => me.roles.some((r) => r !== "exam_office" && r !== "library"),
  },
  {
    href: "/queue",
    label: "Queue",
    show: (me) => me.roles.some((r) => r !== "scholar"),
  },
  {
    href: "/seminars",
    label: "Seminars",
    show: (me) => me.roles.some((r) => r !== "exam_office" && r !== "library") || me.faculty_id !== null,
  },
  {
    href: "/todos",
    label: "My to-dos",
    show: (me) => me.scholar_id !== null,
  },
  {
    href: "/register",
    label: "Register",
    show: (me) => me.roles.some((r) => r !== "library"),
  },
  { href: "/faculty", label: "Faculty", show: () => true },
  { href: "/settings", label: "Settings", show: (me) => me.is_root_admin },
];

export default function AppLayout({ children }: { children: ReactNode }) {
  const { me, loading, error, logout } = useSession();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !me && !error) router.replace("/login?expired=1");
  }, [me, loading, error, router]);

  if (loading) {
    return (
      <main className="shell-loading" aria-busy="true">
        <Owl pose="reading" size={120} label="Loading" />
      </main>
    );
  }
  if (!me) {
    return (
      <main className="shell-loading">
        <ErrorText>{error?.message}</ErrorText>
      </main>
    );
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner clay">
          <Link href="/home" className="wordmark" aria-label="Anveshan home">
            <OwlMark />
            <span>Anveshan</span>
          </Link>
          <nav className="nav" aria-label="Main navigation">
            {NAV.filter((item) => item.show(me)).map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname.startsWith(item.href) ? "page" : undefined}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="topbar-actions">
            <Link href="/notifications" className="btn btn-icon bell"
              aria-label={`Notifications, ${me.unread_notifications} unread`}>
              <span aria-hidden="true">🔔</span>
              {me.unread_notifications > 0 && (
                <span className="bell-count" aria-hidden="true">
                  {me.unread_notifications > 99 ? "99+" : me.unread_notifications}
                </span>
              )}
            </Link>
            <ThemeToggle />
            <Button kind="ghost" onClick={() => logout().then(() => router.replace("/login"))}>
              Log out
            </Button>
          </div>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
  );
}
