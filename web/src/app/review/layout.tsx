"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import type { ReactNode } from "react";
import { Owl } from "@/components/brand/Owl";
import { UniversityMark } from "@/components/brand/UniversityMark";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import "@/components/ui/ui.css";
import "./review.css";

/** The whole of a reviewer's account: no menu, because there is nowhere else to go. */
export default function ReviewLayout({ children }: { children: ReactNode }) {
  const { me, loading, logout } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/login");
    else if (!me.is_reviewer) router.replace("/home");
  }, [me, loading, router]);

  if (!me?.is_reviewer) {
    return <main className="empty-state" aria-busy="true"><Owl pose="reading" size={110} label="Loading" /></main>;
  }
  return (
    <div className="review-shell">
      <header className="review-top">
        <UniversityMark />
        <div className="row">
          <ThemeToggle />
          <Button kind="ghost" onClick={() => logout()}>Log out</Button>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}
