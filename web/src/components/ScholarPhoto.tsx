"use client";

import { useState } from "react";
import type { ChangeEvent } from "react";
import { Button, ErrorText } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { shrink } from "@/lib/image";
import type { Photo } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./scholar-photo.css";

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");

/** A scholar's photo on their profile. The API says who may change it: the scholar themself or
 *  an admin over their unit. */
export function ScholarPhoto({ scholarId, name }: { scholarId: string; name: string }) {
  const path = `/scholars/${scholarId}/photo`;
  const photo = useFetch<Photo>(path);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await photo.reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (file) run(async () => api(path, { method: "PUT", body: await shrink(file) }));
  };

  const image = photo.data?.image;
  return (
    <div className="scholar-photo">
      {image ? (
        <img className="scholar-photo-img" src={image} alt={`Photo of ${name}`} width={112} height={112} />
      ) : (
        <span className="scholar-photo-img scholar-photo-none" aria-label={`No photo of ${name}`} role="img">{initials(name)}</span>
      )}
      {photo.data?.can_change && (
        <div className="scholar-photo-actions">
          <label className={`btn btn-ghost photo-pick${busy ? " is-busy" : ""}`}>
            {image ? "Change photo" : "Add a photo"}
            <input className="visually-hidden" type="file" accept="image/png,image/jpeg" disabled={busy} onChange={upload} />
          </label>
          {image && <Button kind="ghost" disabled={busy} onClick={() => run(() => api(path, { method: "DELETE" }))}>Remove</Button>}
        </div>
      )}
      <ErrorText>{error ?? photo.error}</ErrorText>
    </div>
  );
}
