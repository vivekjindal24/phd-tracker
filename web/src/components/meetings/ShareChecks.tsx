"use client";

import { SHARE_LABELS } from "@/lib/types";
import type { MeetingShare } from "@/lib/types";

/** Who above may read the minutes — set only by the main supervisor (PRD F7). */
export function ShareChecks({
  value,
  onChange,
  disabled,
}: {
  value: MeetingShare[];
  onChange: (next: MeetingShare[]) => void;
  disabled?: boolean;
}) {
  const toggle = (key: MeetingShare) =>
    onChange(value.includes(key) ? value.filter((v) => v !== key) : [...value, key]);
  return (
    <fieldset className="share-checks" disabled={disabled}>
      <legend>Share minutes with</legend>
      {(Object.keys(SHARE_LABELS) as MeetingShare[]).map((key) => (
        <label key={key}>
          <input type="checkbox" checked={value.includes(key)} onChange={() => toggle(key)} />
          {SHARE_LABELS[key]}
        </label>
      ))}
      <p className="field-hint">Unticked groups see only that the meeting happened.</p>
    </fieldset>
  );
}
