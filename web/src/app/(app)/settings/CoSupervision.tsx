"use client";

import { Card } from "@/components/ui/kit";
import type { CoSupervision as Mode } from "@/lib/types";
import type { Save } from "./save";

const OPTIONS: { value: Mode; label: string; hint: string }[] = [
  { value: "off", label: "Off", hint: "Scholars have one supervisor." },
  { value: "view", label: "View", hint: "A co-supervisor sees and logs meetings; only the supervisor approves." },
  { value: "approve", label: "View + approve", hint: "A co-supervisor may also act on the Supervisor step." },
];

export function CoSupervision({ value, save }: { value: Mode; save: Save }) {
  return (
    <Card>
      <fieldset className="segmented">
        <legend>
          <h2>Co-supervision</h2>
        </legend>
        {OPTIONS.map((o) => (
          <label key={o.value} className={value === o.value ? "chosen" : undefined}>
            <input
              type="radio"
              name="co_supervision"
              value={o.value}
              checked={value === o.value}
              onChange={() => save("/settings", "PATCH", { co_supervision: o.value }).catch(() => {})}
            />
            <strong>{o.label}</strong>
            <span>{o.hint}</span>
          </label>
        ))}
      </fieldset>
    </Card>
  );
}
