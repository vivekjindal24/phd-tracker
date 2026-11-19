"use client";

import { useState } from "react";
import { CommitteeCard } from "@/components/CommitteeCard";
import { ErrorText, Field, PageHeader } from "@/components/ui/kit";
import type { OrgUnit } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";

const depth = (u: OrgUnit) => u.path.split(".").length - 1;

/** Each department's research committee, in versions (PRD F9b). A scholar sees their own
 *  department's; other roles pick any unit of the tree. */
export default function CommitteesPage() {
  const { data: units, error } = useFetch<OrgUnit[]>("/org-units");
  const [picked, setPicked] = useState<string | null>(null);
  const unitId = picked ?? units?.find((u) => u.kind.toLowerCase() === "department")?.id ?? units?.[0]?.id;

  return (
    <>
      <PageHeader eyebrow="People" title="Department committees" />
      <div className="toolbar">
        <Field label="Department">
          <select value={unitId ?? ""} onChange={(e) => setPicked(e.target.value)}>
            {units?.map((u) => (
              <option key={u.id} value={u.id}>{"  ".repeat(depth(u))}{u.name}</option>
            ))}
          </select>
        </Field>
      </div>
      <ErrorText>{error}</ErrorText>
      {unitId && <CommitteeCard key={unitId} path={`/org-units/${unitId}/committee`} department />}
    </>
  );
}
