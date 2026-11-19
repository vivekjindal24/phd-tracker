"use client";

import { Field } from "@/components/ui/kit";
import { EXAMINER_ORIGIN_LABELS } from "@/lib/types";
import type { ExaminerOrigin } from "@/lib/types";

/** National or international examiner; "" is not stated. The PhD file lists them apart. */
export function OriginSelect({ value, onChange }: { value: ExaminerOrigin | ""; onChange: (v: ExaminerOrigin | "") => void }) {
  return (
    <Field label="Examiner from">
      <select value={value} onChange={(e) => onChange(e.target.value as ExaminerOrigin | "")}>
        <option value="">Not stated</option>
        {(Object.keys(EXAMINER_ORIGIN_LABELS) as ExaminerOrigin[]).map((o) => <option key={o} value={o}>{EXAMINER_ORIGIN_LABELS[o]}</option>)}
      </select>
    </Field>
  );
}
