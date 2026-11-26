// Finding a paper's own DOI in what its PDF says about itself. Pure, so it is tested without a PDF.

const DOI = /10\.\d{4,9}\/[^\s"'<>]+/i;
const TRAILING = /[.,;:)\]}>]+$/;

/** The first DOI in a text or a doi.org link, without trailing punctuation. */
export function doiIn(text: string): string | null {
  let s = text;
  try {
    s = decodeURIComponent(text);
  } catch {
    // not URL-encoded: read it as it is
  }
  const m = s.match(DOI);
  return m ? m[0].replace(TRAILING, "") : null;
}

/** The paper's own DOI: from its metadata first, then the first page's text, then the first
 *  page's doi.org links. Later pages are left alone: their DOIs are mostly references. */
export function pickDoi(metadata: string[], firstPageText: string, firstPageLinks: string[]): string | null {
  for (const source of [...metadata, firstPageText, ...firstPageLinks.filter((l) => /doi\.org\//i.test(l))]) {
    const found = doiIn(source);
    if (found) return found;
  }
  return null;
}
