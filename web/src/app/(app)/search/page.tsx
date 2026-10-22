"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { Owl } from "@/components/brand/Owl";
import { Card, ErrorText, PageHeader } from "@/components/ui/kit";
import { useFetch } from "@/lib/useFetch";

type Hit = { title: string; detail: string | null; link: string };
const GROUPS: [string, string][] = [
  ["scholars", "Scholars"], ["faculty", "Faculty"], ["reports", "Progress reports"],
  ["meetings", "Meetings"], ["decisions", "Committee decisions"], ["seminars", "Seminars"],
];

function Results() {
  const q = (useSearchParams().get("q") ?? "").trim();
  const { data, error } = useFetch<Record<string, Hit[]>>(q.length >= 2 ? `/search?q=${encodeURIComponent(q)}` : null);
  const total = data ? Object.values(data).reduce((n, g) => n + g.length, 0) : 0;
  return (
    <>
      <PageHeader eyebrow="Search" title={q ? `Results for “${q}”` : "Search"} />
      {q.length < 2 && <p className="muted">Type at least two characters in the search box above.</p>}
      <ErrorText>{error}</ErrorText>
      {data && total === 0 && (
        <Card className="empty-state"><Owl pose="reading" size={96} /><p>Nothing found that you can see.</p></Card>
      )}
      <div className="dash-grid">
        {data && GROUPS.filter(([k]) => (data[k] ?? []).length > 0).map(([k, label]) => (
          <Card key={k}>
            <h2 style={{ fontSize: "var(--text-lg)", marginBottom: "var(--space-3)" }}>{label}</h2>
            <ul className="plain-list">
              {data[k]!.map((h, i) => (
                <li key={`${h.link}-${i}`}><Link href={h.link}>{h.title}</Link>
                  {h.detail && <span className="muted"> · {h.detail}</span>}</li>
              ))}
            </ul>
          </Card>
        ))}
      </div>
    </>
  );
}

export default function SearchPage() {
  return <Suspense><Results /></Suspense>;
}
