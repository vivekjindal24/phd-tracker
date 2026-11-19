"use client";

import { useRef, useState } from "react";
import { Button, ErrorText } from "@/components/ui/kit";
import { download } from "@/lib/api";
import { errorText } from "@/lib/useFetch";

/** One file download (export service, or the API for templates) (ARCHITECTURE.md §2): busy while the PDF/CSV renders,
 *  the server's own message on failure. `signable`: a form that carries signatures asks first whether to print them
 *  in, or leave blank lines for signing the printed copy by hand (`?signed=0`). */
export function DownloadButton({
  path,
  children,
  from = "export",
  signable = false,
}: {
  path: string;
  children: string;
  from?: "export" | "api";
  signable?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ask = useRef<HTMLDialogElement>(null);

  async function go(target: string) {
    ask.current?.close();
    setBusy(true);
    setError(null);
    try {
      await download(target, from);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  const withSigned = (signed: boolean) => `${path}${path.includes("?") ? "&" : "?"}signed=${signed ? 1 : 0}`;

  return (
    <span className="download">
      <Button kind="secondary" disabled={busy} onClick={() => (signable ? ask.current?.showModal() : go(path))}>
        {busy ? "Preparing…" : children}
      </Button>
      <ErrorText>{error}</ErrorText>
      {signable && (
        <dialog ref={ask} className="ask" aria-labelledby="ask-signed">
          <h2 id="ask-signed">Download signed or unsigned?</h2>
          <p>Signed prints the signatures on record. Unsigned leaves a signature and date line for each person, to sign the printed copy by hand and upload the scan.</p>
          <div className="ask-actions">
            <Button kind="primary" onClick={() => go(withSigned(true))}>Signed</Button>
            <Button kind="secondary" onClick={() => go(withSigned(false))}>Unsigned</Button>
            <Button kind="ghost" onClick={() => ask.current?.close()}>Cancel</Button>
          </div>
        </dialog>
      )}
    </span>
  );
}
