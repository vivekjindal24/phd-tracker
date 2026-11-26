// Reads a paper's DOI out of its PDF in the browser, before the file is uploaded anywhere.
import { pickDoi } from "./doi";

const asText = (v: unknown): string => (v == null ? "" : Array.isArray(v) ? v.join(" ") : String(v));

/** The DOI the PDF gives for itself, or null. A scanned paper has no text, so it finds none. */
export async function doiFromPdf(file: File): Promise<string | null> {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
  const doc = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  try {
    const { info, metadata } = await doc.getMetadata();
    const fields = (info ?? {}) as Record<string, unknown>;
    const custom = (fields.Custom ?? {}) as Record<string, unknown>;
    const meta = [
      asText(metadata?.get("prism:doi")),
      asText(metadata?.get("dc:identifier")),
      asText(custom.doi ?? custom.DOI),
      asText(fields.Subject),
    ];
    const page = await doc.getPage(1);
    const text = (await page.getTextContent()).items.map((i) => ("str" in i ? i.str : "")).join(" ");
    const links = (await page.getAnnotations()).map((a: { url?: string }) => a.url ?? "");
    return pickDoi(meta, text, links);
  } finally {
    await doc.destroy();
  }
}
