"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button, ErrorText, Field, PageHeader } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { DESIGNATIONS } from "@/lib/types";
import type { Designation, OrgUnit } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import "./people.css";

type Kind = "scholar" | "faculty";

export default function AddPersonPage() {
  const { me } = useSession();
  const router = useRouter();
  const { data: units } = useFetch<OrgUnit[]>("/org-units");
  const [kind, setKind] = useState<Kind>("scholar");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [unitId, setUnitId] = useState("");
  const [roll, setRoll] = useState("");
  const [designation, setDesignation] = useState<Designation>("Assistant Professor");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Offer only units this admin manages; the API re-checks.
  const adminPaths = me?.unit_roles.filter((r) => r.role === "admin").map((r) => r.unit_path) ?? [];
  const myUnits = (units ?? []).filter((u) =>
    adminPaths.some((p) => u.path === p || u.path.startsWith(`${p}.`)),
  );

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const profile = kind === "scholar"
      ? { scholar: { unit_id: unitId, roll_number: roll } }
      : { faculty: { unit_id: unitId, designation } };
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ email, full_name: name, password, ...profile }),
      });
      router.push(kind === "scholar" ? "/scholars" : "/faculty");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader eyebrow="Directory" title="Add person" />
      <form className="clay card person-form" onSubmit={submit}>
        <fieldset className="kind-picker">
          <legend className="visually-hidden">Type of person</legend>
          {(["scholar", "faculty"] as Kind[]).map((k) => (
            <label key={k} className={kind === k ? "chosen" : undefined}>
              <input type="radio" name="kind" checked={kind === k} onChange={() => setKind(k)} />
              {k === "scholar" ? "Scholar" : "Faculty member"}
            </label>
          ))}
        </fieldset>
        <Field label="Full name">
          <input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Email">
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label="Initial password" hint="At least 10 characters. Share it with them privately; they can change it after logging in.">
          <input type="text" required minLength={10} value={password}
            onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" />
        </Field>
        <Field label="Department / unit">
          <select required value={unitId} onChange={(e) => setUnitId(e.target.value)}>
            <option value="" disabled>Choose…</option>
            {myUnits.map((u) => (
              <option key={u.id} value={u.id}>{u.name}</option>
            ))}
          </select>
        </Field>
        {kind === "scholar" ? (
          <Field label="Roll number">
            <input required maxLength={50} value={roll} onChange={(e) => setRoll(e.target.value)} />
          </Field>
        ) : (
          <Field label="Designation" hint="Sets the UGC supervision limit (8 / 6 / 4).">
            <select value={designation} onChange={(e) => setDesignation(e.target.value as Designation)}>
              {DESIGNATIONS.map((d) => <option key={d}>{d}</option>)}
            </select>
          </Field>
        )}
        <ErrorText>{error}</ErrorText>
        <Button kind="primary" type="submit" disabled={busy}>
          {busy ? "Adding…" : `Add ${kind === "scholar" ? "scholar" : "faculty member"}`}
        </Button>
      </form>
    </>
  );
}
