"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api, ApiError, BRANDING_CHANGED } from "@/lib/api";
import type { OrgUnit } from "@/lib/types";

const depth = (u: OrgUnit) => u.path.split(".").length - 1;

export function OrgTree() {
  const [units, setUnits] = useState<OrgUnit[]>([]);
  const [parentId, setParentId] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("Department");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const rows = await api<OrgUnit[]>("/org-units");
      setUnits(rows);
      setParentId((current) => current || rows[0]?.id || "");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }, []);
  useEffect(() => {
    load();
    window.addEventListener(BRANDING_CHANGED, load);
    return () => window.removeEventListener(BRANDING_CHANGED, load);
  }, [load]);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/org-units", {
        method: "POST",
        body: JSON.stringify({ parent_id: parentId, name, kind, code }),
      });
      setName("");
      setCode("");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function change(unit: OrgUnit, body: Partial<Pick<OrgUnit, "cross_unit_directory" | "aishe_discipline">>) {
    setError(null);
    try {
      await api(`/org-units/${unit.id}`, { method: "PATCH", body: JSON.stringify(body) });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function remove(unit: OrgUnit) {
    setError(null);
    try {
      await api(`/org-units/${unit.id}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  return (
    <Card className="settings-tree">
      <h2>University structure</h2>
      <ul className="tree">
        {units.map((u) => (
          <li key={u.id} style={{ paddingInlineStart: `${depth(u) * 24}px` }}>
            <span className="tree-name">{u.name}</span>
            <span className="badge">{u.kind}</span>
            <code>{u.code}</code>
            {u.parent_id && (
              <label className="tree-toggle">
                <input
                  type="checkbox"
                  checked={u.cross_unit_directory}
                  onChange={(e) => change(u, { cross_unit_directory: e.target.checked })}
                />
                Sees all departments
              </label>
            )}
            {u.parent_id && (
              <input className="tree-discipline" aria-label={`AISHE discipline of ${u.name}`} placeholder="AISHE discipline"
                maxLength={200} defaultValue={u.aishe_discipline ?? ""} key={u.aishe_discipline ?? ""}
                title="The discipline AISHE files this unit's Ph.D. scholars under, as AISHE names it"
                onBlur={(e) => {
                  const value = e.target.value.trim() || null;
                  if (value !== u.aishe_discipline) change(u, { aishe_discipline: value });
                }} />
            )}
            {u.parent_id && (
              <Button kind="ghost" onClick={() => remove(u)} aria-label={`Remove ${u.name}`}>
                Remove
              </Button>
            )}
          </li>
        ))}
      </ul>
      <form className="tree-form" onSubmit={add}>
        <h3>Add a unit</h3>
        <Field label="Inside">
          <select value={parentId} onChange={(e) => setParentId(e.target.value)} required>
            {units.map((u) => (
              <option key={u.id} value={u.id}>
                {"— ".repeat(depth(u))}
                {u.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Name">
          <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
        </Field>
        <Field label="Kind" hint="e.g. School, Faculty, Department, Centre">
          <input value={kind} onChange={(e) => setKind(e.target.value)} required maxLength={200} />
        </Field>
        <Field label="Short code" hint="Letters, digits, - or _ (e.g. CSE)">
          <input value={code} onChange={(e) => setCode(e.target.value)} required
            pattern="[A-Za-z0-9_\-]{1,32}" />
        </Field>
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy || !parentId}>
          Add unit
        </Button>
      </form>
    </Card>
  );
}
