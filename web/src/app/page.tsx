"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useSession } from "@/lib/session";

export default function Index() {
  const { me, loading } = useSession();
  const router = useRouter();
  useEffect(() => {
    if (!loading) router.replace(me ? "/home" : "/login");
  }, [me, loading, router]);
  return null;
}
