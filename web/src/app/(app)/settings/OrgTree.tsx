"use client";

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api, ApiError } from "@/lib/api";
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
