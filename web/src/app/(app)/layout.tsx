"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { Owl, OwlMark } from "@/components/brand/Owl";
import { Nav } from "@/components/Nav";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button, ErrorText } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import "./shell.css";

export default function AppLayout({ children }: { children: ReactNode }) {
  const { me, loading, error, logout } = useSession();
  const router = useRouter();

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
          <Nav me={me} />
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
