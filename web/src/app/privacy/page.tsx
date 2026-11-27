"use client";

import Link from "next/link";
import { UniversityMark } from "@/components/brand/UniversityMark";
import { NoticeText } from "@/components/privacy/NoticeText";
import { formatDate } from "@/lib/format";
import type { PrivacyNotice } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "@/components/ui/ui.css";
import "@/components/privacy/privacy.css";

/** The privacy notice, open to anyone, signed in or not. */
export default function PrivacyPage() {
  const { data, error } = useFetch<PrivacyNotice>("/privacy");
  return (
    <main className="privacy-gate page">
      <UniversityMark />
      <h1>Privacy notice</h1>
      {error && <p role="alert">The notice could not be loaded. Please try again.</p>}
      {data && (
        <>
          {data.changed_at && <p className="muted">Last changed {formatDate(data.changed_at)}</p>}
          <NoticeText notice={data} />
        </>
      )}
      <p><Link href="/home">Back to Anveshan</Link></p>
    </main>
  );
}
