/** Prints a reviewer copy's random code on every page (PRD M3). The code holds no details: only
 *  the API can say whose copy it was. Small and repeated, so a screenshot or a crop keeps one. */
import { degrees, PDFDocument, rgb, StandardFonts } from "pdf-lib";

const SIZE = 8;
const MARGIN = 14;
const GREY = rgb(0.55, 0.55, 0.55);

export class UnstampablePdf extends Error {}

export async function stampPdf(bytes: Uint8Array, code: string): Promise<Buffer> {
  const doc = await PDFDocument.load(bytes).catch(() => {
    throw new UnstampablePdf("This thesis PDF is locked or damaged, so a copy cannot be prepared.");
  });
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (const page of doc.getPages()) {
    const { width, height } = page.getSize();
    const textWidth = font.widthOfTextAtSize(code, SIZE);
    const style = { size: SIZE, font, color: GREY, opacity: 0.8 };
    page.drawText(code, { ...style, x: MARGIN, y: MARGIN });
    page.drawText(code, { ...style, x: width - textWidth - MARGIN, y: height - MARGIN - SIZE });
    page.drawText(code, { ...style, x: width / 2, y: height / 2, opacity: 0.25, rotate: degrees(45) });
  }
  return Buffer.from(await doc.save());
}
