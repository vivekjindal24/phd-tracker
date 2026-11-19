"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatMonth } from "@/lib/format";
import type { ComprehensiveResult, ComprehensiveView } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";

const RESULT_LABELS: Record<ComprehensiveResult, string> = { satisfactory: "Satisfactory", unsatisfactory: "Unsatisfactory" };

/** Form VI: each attempt at the comprehensive examination, its month and result. The admin over
 *  the scholar's unit or the Research Office records them; a satisfactory one ends them. */
export function ComprehensiveCard({ scholarId }: { scholarId: string }) {
  const path = `/scholars/${scholarId}/comprehensive`;
  const { data: v, error, setData } = useFetch<ComprehensiveView>(path);
  const [month, setMonth] = useState("");
  const [result, setResult] = useState<ComprehensiveResult>("satisfactory");
  const [actError, setActError] = useState<string | null>(null);
  if (error) return <ErrorText>{error}</ErrorText>;
  if (!v) return null;

  async function run(to: string, method: "POST" | "DELETE", body?: object) {
    setActError(null);
    try {
      setData(await api<ComprehensiveView>(to, { method, body: body ? JSON.stringify(body) : undefined }));
      setMonth("");
    } catch (e) {
      setActError(errorText(e));
    }
  }
  const add = (e: FormEvent) => {
    e.preventDefault();
    run(path, "POST", { held_in: `${month}-01`, result });
  };
  const last = v.attempts.at(-1);

  return (
    <Card className="coursework">
      <h2>Comprehensive examination</h2>
      {v.attempts.length === 0 ? <p className="muted">No attempt recorded yet.</p> : (
        <ul className="plain-list">
          {v.attempts.map((a) => (
            <li key={a.id}>
              <strong>Attempt {a.attempt}</strong> · {formatMonth(a.held_in)} · {RESULT_LABELS[a.result]}
              {a.notes && <span className="muted"> · {a.notes}</span>}
              {v.can_manage && a.id === last?.id && <Button kind="ghost" onClick={() => run(`/comprehensive-exams/${a.id}`, "DELETE")}>Remove</Button>}
            </li>
          ))}
        </ul>
      )}
      {v.can_manage && !v.passed && (
        <form className="verify" onSubmit={add}>
          <h3>Record attempt {v.attempts.length + 1}</h3>
          <div className="row">
            <Field label="Month held"><input type="month" required value={month} onChange={(e) => setMonth(e.target.value)} /></Field>
            <Field label="Result">
              <select value={result} onChange={(e) => setResult(e.target.value as ComprehensiveResult)}>
                {(Object.keys(RESULT_LABELS) as ComprehensiveResult[]).map((r) => <option key={r} value={r}>{RESULT_LABELS[r]}</option>)}
              </select>
            </Field>
          </div>
          <Button kind="secondary" type="submit">Record</Button>
        </form>
      )}
      <ErrorText>{actError}</ErrorText>
    </Card>
  );
}
