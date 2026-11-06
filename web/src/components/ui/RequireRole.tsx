"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Owl } from "@/components/brand/Owl";
import { Card } from "@/components/ui/kit";
import { useSession } from "@/lib/session";
import type { Me } from "@/lib/types";

/** The 403 state for a page the API would refuse anyway; the API stays the enforcer. */
export function NotForYourRole() {
  return (
    <Card className="empty-state">
      <Owl pose="empty" size={110} />
      <h2>This page isn&apos;t for your role</h2>
      <p>Ask your department admin if you think you should have access.</p>
      <Link href="/home">Back to home</Link>
    </Card>
  );
}

export function RequireRole({ roles, children }: { roles: Me["roles"]; children: ReactNode }) {
  const { me } = useSession();
  return me?.roles.some((r) => roles.includes(r)) ? children : <NotForYourRole />;
}
