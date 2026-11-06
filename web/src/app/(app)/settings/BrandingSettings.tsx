"use client";

import { useState } from "react";
import type { ChangeEvent, FormEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api, logoUrl } from "@/lib/api";
import type { Branding, SettingsData } from "@/lib/types";
import { errorText, useFetch } from "@/lib/useFetch";
import type { Save } from "./save";

/** The name comes from the root unit in the tree below; this card adds address and logo. */
export function BrandingSettings({ data, save }: { data: SettingsData; save: Save }) {
  const branding = useFetch<Branding>("/branding");
  const [address, setAddress] = useState(data.university_address);
  const [error, setError] = useState<string | null>(null);

  async function run(work: () => Promise<unknown>) {
    setError(null);
    try {
      await work();
      await branding.reload();
    } catch (e) {
      setError(errorText(e));
    }
  }

  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) run(() => api("/settings/logo", { method: "PUT", body: file }));
  };
  const saveAddress = (e: FormEvent) => {
    e.preventDefault();
    run(() => save("/settings", "PATCH", { university_address: address }));
  };

  return (
    <Card>
      <h2>University identity</h2>
      <p className="muted">Shown at login, in the top bar and on every PDF. The name is the top unit in the tree.</p>
      <form onSubmit={saveAddress}>
        <Field label="Address on PDFs">
          <input maxLength={500} value={address} onChange={(e) => setAddress(e.target.value)} />
        </Field>
        <Button kind="secondary" type="submit">Save address</Button>
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
      <ErrorText>{error}</ErrorText>
    </Card>
  );
}
