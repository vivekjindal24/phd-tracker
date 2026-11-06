"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { UniversityMark } from "@/components/brand/UniversityMark";
import { Nav } from "@/components/Nav";
import { ThemeToggle } from "@/components/ThemeToggle";
import { BusyBar } from "@/components/ui/BusyBar";
import { Button, ErrorText } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import "./shell.css";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { me, loading, error, loggedOut, logout } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (me?.is_reviewer) router.replace("/review");
    if (loading || me || error) return;
    const here = encodeURIComponent(window.location.pathname + window.location.search);
    router.replace(loggedOut ? "/login" : `/login?expired=1&next=${here}`);
  }, [me, loading, error, loggedOut, router]);

  if (loading || me?.is_reviewer) {
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
      <BusyBar />
      <header className="topbar">
        <div className="topbar-inner clay">
          <Link href="/home" className="wordmark" aria-label="Anveshan home">
            <OwlMark />
            <span>Anveshan</span>
          </Link>
          <UniversityMark />
          <Nav me={me} />
          <form className="topbar-search" role="search" action="/search">
            <label className="visually-hidden" htmlFor="topbar-q">Search</label>
            <input id="topbar-q" name="q" type="search" placeholder="Search…" minLength={2} />
          </form>
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
            <Button kind="ghost" onClick={logout}>Log out</Button>
          </div>
        </div>
      </header>
      <main className="page">{children}</main>
    </>
  );
}
