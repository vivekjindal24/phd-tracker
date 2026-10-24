"use client";

import { useState } from "react";
import { Button, Field } from "@/components/ui/kit";
import type { Scholar } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

/** Find a scholar by name or roll number; the API returns only scholars the caller may see. */
export function ScholarSearch({ label = "Find a scholar", onPick }: { label?: string; onPick: (s: Scholar) => void }) {
  const [q, setQ] = useState("");
  const { data } = useFetch<Scholar[]>(q.length >= 2 ? `/scholars?q=${encodeURIComponent(q)}&limit=10` : null);
  return (
    <>
      <Field label={label} hint="Name or roll number">
        <input value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      {data && (
        <ul className="plain-list">
          {data.map((s) => (
            <li key={s.id}><Button kind="ghost" onClick={() => { onPick(s); setQ(""); }}>{s.full_name} · {s.roll_number} · {s.unit.name}</Button></li>
          ))}
        </ul>
      )}
    </>
  );
}
