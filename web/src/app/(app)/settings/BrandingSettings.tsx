"use client";

import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api, BRANDING_CHANGED, logoUrl } from "@/lib/api";
import type { Branding, OrgUnit, SettingsData } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import type { Save } from "./save";

/** The one place for the university's name, address and logo. The name is stored on the root
 *  unit, so renaming there also renames the top of the tree. */
export function BrandingSettings({ data, save }: { data: SettingsData; save: Save }) {
  const branding = useFetch<Branding>("/branding");
  const units = useFetch<OrgUnit[]>("/org-units");
  const root = units.data?.find((u) => !u.parent_id);
  const [typedName, setTypedName] = useState<string | null>(null);
  const name = typedName ?? root?.name ?? "";
  const [address, setAddress] = useState(data.university_address);
  const [error, setError] = useState<string | null>(null);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    try {
      await work();
      await branding.reload();
      window.dispatchEvent(new Event(BRANDING_CHANGED));
    } catch (e) {
      setError(errorText(e));
    }
  }

  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) run(() => api("/settings/logo", { method: "PUT", body: file }));
  };
  const saveDetails = (e: FormEvent) => {
    e.preventDefault();
    run(async () => {
      if (root && name !== root.name) {
        await api(`/org-units/${root.id}`, { method: "PATCH", body: JSON.stringify({ name }) });
        await units.reload();
        setTypedName(null);
      }
      await save("/settings", "PATCH", { university_address: address });
    });
  };

  return (
    <Card>
      <h2>University identity</h2>
      <p className="muted">Set these once here. They appear across the portal and on every PDF.</p>
      <form onSubmit={saveDetails}>
        <Field label="University name">
          <input required maxLength={200} disabled={!root} value={name} onChange={(e) => setTypedName(e.target.value)} />
        </Field>
        <Field label="Address on PDFs">
          <input maxLength={500} value={address} onChange={(e) => setAddress(e.target.value)} />
        </Field>
        <Button kind="secondary" type="submit" disabled={!root}>Save details</Button>
      </form>
      {branding.data?.has_logo && (
        <img src={logoUrl(branding.data.logo_version)} alt={`${branding.data.university} logo`} height={72} />
      )}
      <Field label="Logo (PNG or JPEG, up to 500 KB)">
        <input type="file" accept="image/png,image/jpeg" onChange={upload} />
      </Field>
      {branding.data?.has_logo && (
        <Button kind="ghost" onClick={() => run(() => api("/settings/logo", { method: "DELETE" }))}>Remove logo</Button>
      )}
      <ErrorText>{error ?? units.error}</ErrorText>
    </Card>
  );
}
