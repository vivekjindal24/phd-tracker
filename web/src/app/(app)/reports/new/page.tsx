"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import type { ItemView, Period } from "@/lib/types";
import { errorText } from "@/lib/useFetch";

function currentPeriod(): { year: number; period: Period } {
  const now = new Date();
  return { year: now.getFullYear(), period: now.getMonth() < 6 ? "January-June" : "July-December" };
}

export default function NewReportPage() {
  const router = useRouter();
  const initial = currentPeriod();
  const [year, setYear] = useState(initial.year);
  const [period, setPeriod] = useState<Period>(initial.period);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const item = await api<ItemView>("/reports", {
        method: "POST",
        body: JSON.stringify({ report_year: year, period, summary }),
      });
      router.push(`/items/progress_report/${item.id}`);
    } catch (err) {
      setError(errorText(err));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Six-monthly progress" title="New progress report" />
      <form className="clay card" style={{ display: "grid", gap: "var(--space-4)", maxWidth: 760 }} onSubmit={submit}>
        <div className="row">
          <Field label="Period">
            <select value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
              <option value="January-June">January–June</option>
              <option value="July-December">July–December</option>
            </select>
          </Field>
          <Field label="Year">
            <input type="number" min={2000} max={2100} required value={year}
              onChange={(e) => setYear(Number(e.target.value))} />
          </Field>
        </div>
        <Field label="Summary of progress" hint="What you did this period, results, and plans for the next. Saved as a draft; you submit it when ready.">
          <textarea required minLength={20} maxLength={20000} value={summary}
            style={{ minHeight: 240, resize: "vertical" }} onChange={(e) => setSummary(e.target.value)} />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy}>{busy ? "Saving…" : "Save draft"}</Button>
      </form>
    </>
  );
}
