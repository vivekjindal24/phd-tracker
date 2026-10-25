"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/session";

/** A signed-in visitor to `/` goes straight to their home page; everyone else stays on the landing page. */
export function SignedInRedirect() {
  const { me } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (me) router.replace("/home");
  }, [me, router]);
  return null;
}
