"use client";

import { useEffect, useRef, useState } from "react";
import type { PDFDocumentProxy } from "pdfjs-dist";
import { Button, ErrorText } from "@/components/ui/kit";
import { fileBytes } from "@/lib/api";
import { errorText } from "@/lib/useFetch";

/** Draws the reviewer's stamped copy page by page, with no file link and no download or print
 *  control. This stops casual copying only: the code on each page is what traces a leak. */
export function PdfViewer({ path, page, onPage }: { path: string; page: number; onPage: (p: number) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [doc, setDoc] = useState<PDFDocumentProxy | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    let loaded: PDFDocumentProxy | null = null;
    (async () => {
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
      loaded = await pdfjs.getDocument({ data: await fileBytes(path) }).promise;
      if (dead) void loaded.destroy();
      else setDoc(loaded);
    })().catch((e) => { if (!dead) setError(errorText(e)); });
    return () => {
      dead = true;
      void loaded?.destroy();
    };
  }, [path]);

  useEffect(() => {
    const target = canvas.current;
    const context = target?.getContext("2d");
    if (!doc || !target || !context) return;
    let task: ReturnType<Awaited<ReturnType<PDFDocumentProxy["getPage"]>>["render"]> | null = null;
    let dead = false;
    doc.getPage(page).then((p) => {
      if (dead) return;
      const scale = Math.min(2, (target.parentElement?.clientWidth ?? 800) / p.getViewport({ scale: 1 }).width);
      const viewport = p.getViewport({ scale });
      target.width = viewport.width;
      target.height = viewport.height;
      task = p.render({ canvas: target, canvasContext: context, viewport });
      return task.promise;
    }).catch((e) => {
      if (!dead && e?.name !== "RenderingCancelledException") setError(errorText(e));
    });
    return () => {
      dead = true;
      task?.cancel();
    };
  }, [doc, page]);

  if (error) return <ErrorText>{error}</ErrorText>;
  return (
    <div className="pdf-viewer" onContextMenu={(e) => e.preventDefault()}>
      {!doc && <p className="muted">Preparing your copy…</p>}
      <div className="pdf-page"><canvas ref={canvas} aria-label={`Thesis page ${page}`} /></div>
      {doc && (
        <div className="row pdf-pager">
          <Button kind="secondary" disabled={page <= 1} onClick={() => onPage(page - 1)}>Previous</Button>
          <span aria-live="polite">Page {page} of {doc.numPages}</span>
          <Button kind="secondary" disabled={page >= doc.numPages} onClick={() => onPage(page + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}
