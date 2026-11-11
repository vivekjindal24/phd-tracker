"use client";

import { useState } from "react";
import { useSession } from "@/lib/session";
import type { OrgUnit } from "@/lib/types";
import { useDebounced, useFetch } from "@/lib/useFetch";
import { Field } from "./ui/kit";

/** The search box and department filter shared by every list of scholars' records. The API
 *  applies them inside what the reader may already see (scope.narrow_to_scholars).
 *  `fields` goes in the page's toolbar; `params` are added to the list request. */
export function useScholarFilter(placeholder = "Scholar name or roll number") {
  const { me } = useSession();
  const [q, setQ] = useState("");
  const search = useDebounced(q);
  const [unitId, setUnitId] = useState("");
  const roles = me?.roles ?? [];
  const seesOthers = roles.some((r) => r !== "scholar");
  // A supervisor's scholars are few and theirs; departments matter to heads, admins and offices.
  const seesUnits = roles.some((r) => r !== "scholar" && r !== "supervisor");
  const { data: units } = useFetch<OrgUnit[]>(seesUnits ? "/org-units" : null);
  const departments = (units ?? []).filter((u) => u.parent_id !== null);

  const params: Record<string, string> = {};
  if (search) params.q = search;
  if (unitId) params.unit_id = unitId;

  const fields = seesOthers && (
    <>
      <Field label="Search">
        <input type="search" placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      {departments.length > 1 && (
        <Field label="Department">
          <select value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            <option value="">All</option>
            {departments.map((u) => (
              <option key={u.id} value={u.id}>{"— ".repeat(u.path.split(".").length - 2)}{u.name}</option>
            ))}
          </select>
        </Field>
      )}
    </>
  );
  return { fields, params, active: Boolean(search || unitId) };
}

/** A list path with its filters: `listPath("/reports", { state }, filter.params)`; blanks are dropped. */
export function listPath(path: string, ...groups: Record<string, string>[]): string {
  const query = new URLSearchParams(Object.entries(Object.assign({}, ...groups)).filter(([, v]) => v) as [string, string][]);
  return query.size ? `${path}?${query}` : path;
}
