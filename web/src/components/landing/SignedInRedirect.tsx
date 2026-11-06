"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/session";
import type { Branding } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** A signed-in visitor to `/` goes straight to their home page. A university's own install (it
 *  has set a logo) goes to login: the landing page is for prospective universities. */
export function SignedInRedirect() {
  const { me } = useSession();
  const { data } = useFetch<Branding>("/branding");
  const router = useRouter();
  useEffect(() => {
    if (me) router.replace("/home");
    else if (data?.has_logo) router.replace("/login");
  }, [me, data, router]);
  return null;
}
