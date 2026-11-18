"use client";

import { useState } from "react";
import type { ChangeEvent } from "react";
import { Button, Card, ErrorText, Field } from "@/components/ui/kit";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/format";
import type { Signature } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import "./signature.css";

const MAX_BYTES = 500_000; // the API's cap
const MAX_WIDTH = 800;

/** A phone photo is often past the cap: redraw it smaller, as JPEG on white. */
async function shrink(file: File): Promise<Blob> {
  if (file.size <= MAX_BYTES) return file;
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_WIDTH / bitmap.width);
  const canvas = Object.assign(document.createElement("canvas"), {
    width: Math.round(bitmap.width * scale),
    height: Math.round(bitmap.height * scale),
  });
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("This browser cannot resize the image. Choose one under 500 KB.");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  return new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("The image could not be resized."))), "image/jpeg", 0.85),
  );
}

function status(sig: Signature, self: boolean): string {
  if (sig.confirmed_at) return `Confirmed ${formatWhen(sig.confirmed_at)}. It is used when ${self ? "you sign" : "they sign"}.`;
  return self
    ? "Waiting for your department admin or the Research Office to confirm it. You cannot sign with it until then."
    : "Uploaded by them; waiting for confirmation.";
}

/** One person's specimen signature: their own (self) or, for a keeper, someone else's. A keeper's
 *  upload is the paper signature handed in at the department, so the API confirms it at once. */
export function SignatureCard({ userId, self, onChange }: { userId: string; self: boolean; onChange?: () => void }) {
  const sig = useFetch<Signature | null>(`/users/${userId}/signature`);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const path = `/users/${userId}/signature`;

  async function run(work: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await work();
      await sig.reload();
      onChange?.();
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

  const current = sig.data;
  return (
    <Card>
      <h2>{self ? "My signature" : "Signature"}</h2>
      {current ? (
        <>
          <img className="signature-specimen" src={current.image} alt="Specimen signature" />
          <p className={current.confirmed_at ? undefined : "muted"}>{status(current, self)}</p>
        </>
      ) : (
        <p className="muted">
          {self
            ? "No signature yet. Upload a scan or a clear photo of your signature on white paper; your department admin or the Research Office confirms it. Or sign on paper at your department and they upload it for you."
            : "No signature on file. Upload the paper signature they signed for you; it counts as confirmed."}
        </p>
      )}
      <Field label={current ? "Replace with a new image (PNG or JPEG)" : "Upload an image (PNG or JPEG)"}>
        <input type="file" accept="image/png,image/jpeg" disabled={busy} onChange={upload} />
      </Field>
      {current && !self && !current.confirmed_at && (
        <Button kind="primary" disabled={busy} onClick={() => run(() => api(`${path}/confirm`, { method: "POST" }))}>
          Confirm — it matches their signature
        </Button>
      )}
      {current && (
        <Button kind="ghost" disabled={busy} onClick={() => run(() => api(path, { method: "DELETE" }))}>Remove</Button>
      )}
      <ErrorText>{error ?? sig.error}</ErrorText>
    </Card>
  );
}
