"use client";

import { useState } from "react";
import { Button, ErrorText } from "@/components/ui/kit";
import { download } from "@/lib/api";
import { errorText } from "@/lib/useFetch";

/** One export-service download (ARCHITECTURE.md §2): busy while the PDF/CSV renders,
 *  the server's own message on failure. */
export function DownloadButton({ path, children }: { path: string; children: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function go() {
    setBusy(true);
    setError(null);
    try {
      await download(path);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="download">
      <Button kind="secondary" disabled={busy} onClick={go}>{busy ? "Preparing…" : children}</Button>
      <ErrorText>{error}</ErrorText>
    </span>
  );
}
