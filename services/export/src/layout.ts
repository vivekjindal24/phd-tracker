/** Shared pdfkit layout for both exports — one header/field/table idiom, no per-export CSS. */

import PDFDoc from "pdfkit";

const INK = "#1a1a1a";
const MUTED = "#5a5a5a";
const RULE = "#c9c9c9";

export function newDoc(opts: { landscape?: boolean } = {}): PDFKit.PDFDocument {
	return new PDFDoc({
		size: "A4",
		layout: opts.landscape ? "landscape" : "portrait",
		margins: { top: 56, bottom: 56, left: 56, right: 56 },
		info: { Title: "PhD Tracker export" },
	});
}

export function docTitle(doc: PDFKit.PDFDocument, title: string, subtitle?: string): void {
	doc.fontSize(20).fillColor(INK).text(title);
	if (subtitle) {
		doc.moveDown(0.3).fontSize(10).fillColor(MUTED).text(subtitle);
	}
	doc.moveDown(0.4).moveTo(doc.page.margins.left, doc.y).lineTo(doc.page.width - doc.page.margins.right, doc.y)
		.strokeColor(RULE).lineWidth(1).stroke();
	doc.moveDown(0.8);
}

export function field(doc: PDFKit.PDFDocument, label: string, value: string | null | undefined): void {
	doc.font("Helvetica-Bold").fontSize(10).fillColor(MUTED).text(`${label}: `, { continued: true })
		.font("Helvetica").fillColor(INK).text(value ?? "—");
	doc.moveDown(0.2);
}

export function para(doc: PDFKit.PDFDocument, text: string): void {
	doc.font("Helvetica").fontSize(10).fillColor(INK).text(text);
	doc.moveDown(0.4);
}

/** Minimal grid table; headers repeated automatically on page breaks by the caller's layout. */
export function table(
	doc: PDFKit.PDFDocument,
	headers: string[],
	widths: number[],
	rows: (string | null)[][],
): void {
	const total = widths.reduce((a, b) => a + b, 0);
	const startX = doc.page.margins.left;
	const usable = doc.page.width - startX - doc.page.margins.right;
	const scale = usable / total;
	const cols = widths.map((w) => w * scale);
	const rowHeight = 20;

	const drawRow = (cells: (string | null)[], bold: boolean) => {
		const y = doc.y;
		if (y + rowHeight > doc.page.height - doc.page.margins.bottom) {
			doc.addPage();
		}
		let x = startX;
		cells.forEach((cell, i) => {
			doc.font(bold ? "Helvetica-Bold" : "Helvetica").fontSize(9).fillColor(bold ? MUTED : INK)
				.text(cell ?? "—", x + 3, doc.y, { width: (cols[i] ?? 0) - 6, ellipsis: true, lineBreak: false });
			x += cols[i] ?? 0;
		});
		if (bold) {
			doc.moveTo(startX, y - 2).lineTo(startX + usable, y - 2).strokeColor(RULE).lineWidth(0.5).stroke();
		}
		doc.y = Math.max(doc.y + rowHeight - 9, y + rowHeight);
		doc.moveTo(startX, doc.y - 2).lineTo(startX + usable, doc.y - 2).strokeColor(RULE).lineWidth(0.5).stroke();
	};

	drawRow(headers, true);
	for (const row of rows) drawRow(row, false);
}

/** The never-a-blank-page rule (UX_FLOWS Flow 5): an empty result renders a cover page. */
export function emptyState(doc: PDFKit.PDFDocument, title: string): void {
	docTitle(doc, title);
	doc.moveDown(3).fontSize(12).fillColor(MUTED).text("No records found.", { align: "center" });
}

export function finish(doc: PDFKit.PDFDocument): Promise<Buffer> {
	return new Promise((resolve, reject) => {
		const chunks: Buffer[] = [];
		doc.on("data", (chunk: Buffer) => chunks.push(chunk));
		doc.on("end", () => resolve(Buffer.concat(chunks)));
		doc.on("error", reject);
		doc.end();
	});
}