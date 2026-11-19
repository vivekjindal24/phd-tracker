/** The PhD file (PRD F17): the index first, then each recorded annexure — every entry that has a
 *  form printed as the university's form on a page of its own, the rest summed up together — and
 *  after each entry the scans of its papers signed by hand (F17b). An annexure with nothing to show
 *  is listed with the reason, never left out. */
import { PDFDocument as PDFLibDocument, StandardFonts } from "pdf-lib";
import PDFDocument from "pdfkit";
import type { PhdFileView } from "./api.ts";
import { day, footer, header, keyValues, signatureLines, toBuffer } from "./render.ts";

type Entry = PhdFileView["annexures"][number]["entries"][number];
type Form = NonNullable<Entry["form"]>;

/** A signed copy's scan, fetched by the server from its short-lived link, keyed by the copy's id. */
export type Scan = { bytes: Uint8Array; type: string };
type Placeholder = { page: number; src: PDFLibDocument; index: number };

const INDEX_COLUMNS: [string, number][] = [["S. No.", 38], ["Annexure", 232], ["Date", 68], ["Signed", 52], ["Page", 93]];
const SCAN_MARGIN = 56; // scans stay clear of the footer

/** Signed when every approved entry carries its signatures; blank when nothing needs one. */
function signedMark(entries: Entry[]): string {
  const marks = entries.map((e) => e.signed).filter((s) => s !== null);
  if (marks.length === 0) return "";
  return marks.every(Boolean) ? "Signed" : "Unsigned";
}

/** Puts an approved scan after its entry: an image on a page of its own; a PDF's pages on blank
 *  pages kept for them, drawn in afterwards with pdf-lib. A scan that cannot be read leaves a note,
 *  never a failed file. */
async function drawScan(doc: PDFKit.PDFDocument, heading: string, scan: Scan | undefined, slots: Placeholder[]) {
  const unreadable = () => {
    doc.addPage().font("Helvetica-Oblique").fontSize(10)
      .text(`The signed copy of "${heading}" could not be read here; open it in the portal.`);
  };
  if (!scan) return unreadable();
  if (scan.type === "application/pdf") {
    const src = await PDFLibDocument.load(scan.bytes).catch(() => null);
    if (!src || src.getPageCount() === 0) return unreadable();
    for (let index = 0; index < src.getPageCount(); index++) {
      doc.addPage();
      slots.push({ page: doc.bufferedPageRange().count - 1, src, index });
    }
    return;
  }
  try {
    doc.addPage();
    const { left, right, top, bottom } = doc.page.margins;
    doc.image(Buffer.from(scan.bytes), left, top,
      { fit: [doc.page.width - left - right, doc.page.height - top - bottom], align: "center" });
  } catch (e) {
    console.error("a signed copy could not be drawn:", e);
    doc.text(`The signed copy of "${heading}" could not be read here; open it in the portal.`);
  }
}

async function fillPlaceholders(pdf: Buffer, slots: Placeholder[]): Promise<Buffer> {
  if (slots.length === 0) return pdf;
  const out = await PDFLibDocument.load(pdf);
  const font = await out.embedFont(StandardFonts.HelveticaOblique);
  const margin = SCAN_MARGIN;
  for (const { page, src, index } of slots) {
    const target = out.getPage(page);
    const { width, height } = target.getSize();
    if (!src.getPage(index).node.Contents()) { // nothing pdf-lib can embed (it would fail on save)
      target.drawText(`Page ${index + 1} of this signed copy could not be read here; open it in the portal.`,
        { x: margin, y: height - margin - 10, size: 10, font });
      continue;
    }
    const [embedded] = await out.embedPdf(src, [index]);
    if (!embedded) continue;
    const scale = Math.min((width - 2 * margin) / embedded.width, (height - 2 * margin) / embedded.height);
    const w = embedded.width * scale;
    const h = embedded.height * scale;
    target.drawPage(embedded, { x: (width - w) / 2, y: margin + (height - 2 * margin - h) / 2, width: w, height: h });
  }
  return Buffer.from(await out.save());
}

/** A ruled table; columns share the width by how much text they hold. */
function drawTable(doc: PDFKit.PDFDocument, t: Form["tables"][number]) {
  const left = doc.page.margins.left;
  const span = doc.page.width - left - doc.page.margins.right;
  const weight = t.columns.map((c, i) =>
    Math.min(40, Math.max(4, c.length, ...t.rows.map((r) => (r[i] ?? "").length))));
  const total = weight.reduce((a, b) => a + b, 0);
  const widths = weight.map((w) => (w / total) * span);
  if (t.title) doc.moveDown(0.5).font("Helvetica-Bold").fontSize(10).text(t.title, left);
  doc.moveDown(0.3);
  const row = (cells: string[], bold: boolean) => {
    if (doc.y > doc.page.height - doc.page.margins.bottom - 40) doc.addPage();
    const top = doc.y;
    let x = left;
    let bottom = top;
    doc.font(bold ? "Helvetica-Bold" : "Helvetica").fontSize(9);
    cells.forEach((c, i) => {
      doc.text(c, x + 4, top + 4, { width: widths[i]! - 8 });
      bottom = Math.max(bottom, doc.y + 3);
      x += widths[i]!;
    });
    x = left;
    for (const w of widths) {
      doc.rect(x, top, w, bottom - top).lineWidth(0.5).stroke();
      x += w;
    }
    doc.x = left;
    doc.y = bottom;
  };
  if (t.columns.some((c) => c)) row(t.columns, true);
  for (const r of t.rows) row(r, false);
}

/** One entry as the university's paper form. `signed`: print the specimens of those who signed in
 *  the portal; otherwise only the lines, for signing the printed copy by hand. */
function drawForm(doc: PDFKit.PDFDocument, v: PhdFileView, annexure: number, f: Form, signed: boolean) {
  doc.addPage();
  const left = doc.page.margins.left;
  doc.font("Helvetica").fontSize(8).fillColor("#555555")
    .text(`Annexure ${annexure}`, left, doc.page.margins.top - 24, { align: "right" }).fillColor("black");
  doc.y = doc.page.margins.top;
  header(doc, v, f.title, "");
  keyValues(doc, f.fields);
  for (const t of f.tables) drawTable(doc, t);
  if (f.statement) doc.moveDown(0.8).font("Helvetica").fontSize(10).text(f.statement, left, doc.y, { align: "justify", lineGap: 2 });
  const who = (s: Form["signed_by"][number]) =>
    ({ label: s.name ? `${s.name}\n${s.role}` : s.role, image: signed ? s.signature : null });
  if (f.signed_by.length) {
    if (f.signed_heading) doc.moveDown(1).font("Helvetica-Bold").fontSize(10).text(f.signed_heading, left);
    signatureLines(doc, f.signed_by.map(who), 46, !signed);
  }
  if (f.forwarded) {
    doc.moveDown(0.8).font("Helvetica-Bold").fontSize(10).text(`Forwarded to ${f.forwarded.to}:`, left);
    signatureLines(doc, f.forwarded.by.map(who), 40, !signed, true);
  }
  if (f.copy_to.length) {
    doc.moveDown(0.8).font("Helvetica-Bold").fontSize(9.5).text("Copy to:", left);
    doc.font("Helvetica").fontSize(9.5);
    f.copy_to.forEach((c, i) => doc.text(`${i + 1}. ${c}`, left + 10));
  }
  if (f.recorded) doc.moveDown(0.8).font("Helvetica-Oblique").fontSize(8).fillColor("#555555").text(f.recorded, left).fillColor("black");
}

/** The entries without a form of their own, summed up on one page under the annexure's title. */
function drawSummary(doc: PDFKit.PDFDocument, v: PhdFileView, n: number, title: string, e: Entry, fresh: boolean,
  signed: boolean) {
  const left = doc.page.margins.left;
  if (fresh) {
    doc.addPage();
    doc.font("Helvetica-Bold").fontSize(13).text(`Annexure ${n} — ${title}`);
    doc.font("Helvetica").fontSize(9).fillColor("#444444").text(`${v.scholar} · ${v.roll_number}`).fillColor("black");
    doc.moveDown(0.8);
  } else if (doc.y > doc.page.height - doc.page.margins.bottom - 80) doc.addPage();
  doc.font("Helvetica-Bold").fontSize(11).text(e.heading, left);
  if (e.date) doc.font("Helvetica").fontSize(9).fillColor("#444444").text(day(e.date)).fillColor("black");
  doc.moveDown(0.3);
  keyValues(doc, e.lines);
  const follows = e.papers.filter((p) => p.copy?.scan_url).map((p) => p.label);
  if (signed && follows.length) {
    doc.font("Helvetica-Oblique").fontSize(9).text(`Signed copies follow: ${follows.join("; ")}.`, left);
  } else if (e.signed !== null) {
    doc.font("Helvetica-Oblique").fontSize(9)
      .text(e.signed ? "Approved with signatures on record." : "Approved in the portal without a signature.", left);
  }
  doc.moveDown(0.8);
}

/** `signed`: the signatures and the approved scans in; unsigned, the generated forms alone with
 *  lines to sign, for printing and signing by hand. */
export async function phdFilePdf(v: PhdFileView, scans: Map<string, Scan> = new Map(), signed = true): Promise<Buffer> {
  const doc = new PDFDocument({ size: "A4", margin: 56, bufferPages: true, info: { Title: `PhD file – ${v.scholar}` } });
  header(doc, v, "PhD File", `${v.scholar} · ${v.roll_number} · ${v.unit}`);
  keyValues(doc, [
    ["Supervisor", v.supervisor ?? "—"],
    ["Admitted", day(v.admission_date)],
  ]);
  doc.moveDown(0.6).font("Helvetica-Bold").fontSize(12).text("Index of annexures");
  const indexTop = doc.y + 6;
  const left = doc.page.margins.left;

  const pages: (number | null)[] = [];
  const slots: Placeholder[] = [];
  for (const [i, a] of v.annexures.entries()) {
    if (a.entries.length === 0) {
      pages.push(null);
      continue;
    }
    pages.push(doc.bufferedPageRange().count + 1); // the next page opens the annexure
    let onSummary = false; // whether the current page is this annexure's summary page
    for (const e of a.entries) {
      if (e.form) {
        drawForm(doc, v, i + 1, e.form, signed);
        onSummary = false;
      } else {
        drawSummary(doc, v, i + 1, a.title, e, !onSummary, signed);
        onSummary = true;
      }
      if (!signed) continue;
      for (const p of e.papers) {
        if (!p.copy?.scan_url) continue;
        await drawScan(doc, `${p.label}, ${e.heading}`, scans.get(p.copy.id), slots);
        onSummary = false;
      }
    }
  }

  doc.switchToPage(0);
  const drawRow = (cells: string[], y: number, bold = false) => {
    let x = left;
    doc.font(bold ? "Helvetica-Bold" : "Helvetica").fontSize(9.5);
    cells.forEach((c, i) => {
      doc.text(c, x, y, { width: INDEX_COLUMNS[i]![1] - 6 });
      x += INDEX_COLUMNS[i]![1];
    });
  };
  drawRow(INDEX_COLUMNS.map(([label]) => label), indexTop, true);
  let y = indexTop + 15;
  doc.moveTo(left, y - 3).lineTo(left + INDEX_COLUMNS.reduce((s, [, w]) => s + w, 0), y - 3).lineWidth(0.6).stroke();
  v.annexures.forEach((a, n) => {
    const page = pages[n];
    drawRow([String(n + 1), a.title, a.date ? day(a.date) : "", signedMark(a.entries), page ? String(page) : (a.note ?? "")], y);
    y = Math.max(doc.y, y + 14) + 4;
  });
  footer(doc, v.generated_by, v.generated_at);
  return fillPlaceholders(await toBuffer(doc), slots);
}
