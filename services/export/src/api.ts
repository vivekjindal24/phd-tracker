/** Reads from the API's /internal endpoints with the caller's token forwarded verbatim.
 *  Every response is validated with zod: a malformed upstream is a loud 500, never a
 *  silently blank PDF (CODE_STYLE.md §3). */
import { z } from "zod";
import { setDateFormat } from "./dates.ts";

export class UpstreamError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API answered ${status}`);
  }
}

const brand = {
  university: z.string(),
  address: z.string(),
  logo: z.string().nullable(), // base64 PNG or JPEG
};

const historyEntry = z.object({
  action: z.string(),
  actor: z.string(),
  on_behalf_of: z.string().nullable().default(null), // a stand-in or the head, for the supervisor
  step: z.string().nullable(),
  to: z.string().nullable(),
  comment: z.string().nullable(),
  rating: z.enum(["satisfactory", "needs_improvement", "unsatisfactory"]).nullable(),
  at: z.string(),
  signature: z.string().nullable().default(null), // data: URL of the specimen that signed it (PRD F17b)
});

export const reportView = z.object({
  ...brand,
  unit: z.string().nullable(),
  scholar: z.string(),
  roll_number: z.string(),
  supervisor: z.string().nullable(),
  committee: z.array(z.string()),
  period: z.string(),
  report_year: z.number().int(),
  summary: z.string(),
  sections: z.array(z.object({ name: z.string(), text: z.string() })),
  // The committee's line: may continue with / without assistantship (null: not stated).
  assistantship: z.enum(["with", "without"]).nullable().default(null),
  activity: z.object({
    meetings: z.number().int(),
    publications: z.array(z.string()).nullable(),
    conferences: z.array(z.string()).nullable(),
  }),
  files: z.array(z.string()),
  state: z.enum(["draft", "in_review", "sent_back", "approved"]),
  submitted_at: z.string().nullable(),
  approved_at: z.string().nullable(),
  history: z.array(historyEntry),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type ReportView = z.infer<typeof reportView>;

export const certificateView = z.object({
  ...brand,
  unit: z.string().nullable(),
  serial: z.string(),
  scholar: z.string(),
  roll_number: z.string(),
  degree: z.string(),
  opening: z.string(),
  title_lead: z.string(),
  body: z.string(),
  signatories: z.array(z.string()).min(1),
  thesis_title: z.string(),
  viva_date: z.string(),
  issued_on: z.string(),
  verify_url: z.string().url(),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type CertificateView = z.infer<typeof certificateView>;

export const reviewCopyView = z.object({
  code: z.string(),
  file_url: z.string().url(),
  file_name: z.string(),
  download: z.boolean(),
});
export type ReviewCopyView = z.infer<typeof reviewCopyView>;

export const tableView = z.object({
  ...brand,
  title: z.string(),
  columns: z.array(z.string()),
  rows: z.array(z.array(z.union([z.string(), z.number(), z.null()]))),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type TableView = z.infer<typeof tableView>;

export const registerView = z.object({
  ...brand,
  unit: z.string().nullable(),
  filters: z.object({ milestone_type: z.string().nullable(), status: z.string().nullable() }),
  rows: z.array(
    z.object({
      scholar: z.string(),
      roll_number: z.string(),
      unit: z.string(),
      milestone_type: z.string(),
      status: z.string(),
      approval_body: z.string(),
      resolution_number: z.string().nullable(),
      resolution_date: z.string().nullable(),
      notes: z.string(),
    }),
  ),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type RegisterView = z.infer<typeof registerView>;

const signer = z.object({ name: z.string(), role: z.string(), signature: z.string().nullable() });
/** A generated form (phd_forms.py): particulars, tables, the statement, who signs. */
const form = z.object({
  title: z.string(),
  number: z.string().nullable().default(null), // the university's form number, "Form VII-A"
  intro: z.string().nullable().default(null), // a paragraph above the particulars (a notice)
  fields: z.array(z.tuple([z.string(), z.string()])),
  tables: z.array(z.object({
    title: z.string(), columns: z.array(z.string()), rows: z.array(z.array(z.string())),
    widths: z.array(z.number().positive()).nullable().default(null), // shares of the width, if fixed
    row_height: z.number().positive().max(80).nullable().default(null), // room to sign in a row
  })),
  statement: z.string().nullable(),
  signed_heading: z.string().nullable(),
  signed_by: z.array(signer),
  forwarded: z.object({ to: z.string(), by: z.array(signer) }).nullable(),
  copy_to: z.array(z.string()),
  recorded: z.string().nullable(),
  // The signed paper whose approved scan takes this page's place in the signed file; null: none.
  paper: z.string().nullable().default(null),
});
export type FormView = z.infer<typeof form>;

// The PhD file (PRD F17): every annexure in career order, with its entries or why it has none.
export const phdFileView = z.object({
  ...brand,
  scholar: z.string(),
  roll_number: z.string(),
  unit: z.string(),
  supervisor: z.string().nullable(),
  admission_date: z.string().nullable(),
  annexures: z.array(
    z.object({
      key: z.string(),
      title: z.string(),
      date: z.string().nullable(),
      note: z.string().nullable(), // "Not on record", "Not shown to you", …; null when it has entries
      entries: z.array(
        z.object({
          date: z.string().nullable(),
          heading: z.string(),
          lines: z.array(z.tuple([z.string(), z.string()])),
          signed: z.boolean().nullable(), // approved items only: every approval signed or not
          // Its papers signed by hand (PRD F17b), in the paper file's order; a scan link once approved.
          // The entry printed as the university's paper forms (phd_forms.py), in the paper file's order.
          forms: z.array(form).default([]),
          papers: z.array(z.object({
            kind: z.string(),
            label: z.string(),
            copy: z.object({ id: z.string(), content_type: z.string(), scan_url: z.string().nullable() }).nullable(),
          })).default([]),
        }),
      ),
    }),
  ),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type PhdFileView = z.infer<typeof phdFileView>;

// A seminar's circular or attendance sheet, one page per scholar (PRD F17b), to sign by hand.
export const seminarPaperView = z.object({
  ...brand,
  title: z.string(),
  forms: z.array(form),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type SeminarPaperView = z.infer<typeof seminarPaperView>;

const money = z.number().nonnegative();
export const ucView = z.object({
  ...brand,
  unit: z.string().nullable(),
  title: z.string(),
  agency: z.string(),
  sanction_number: z.string(),
  amount_sanctioned: money,
  pi: z.string().nullable(),
  period_start: z.string(),
  period_end: z.string(),
  opening_balance: z.number(), // negative when spent ahead of the money received
  grants_received: z.array(z.object({ date: z.string(), reference: z.string().nullable(), amount: money })),
  received: money,
  available: z.number(),
  spent_by_head: z.record(z.string(), money),
  spent: money,
  closing_balance: z.number(),
  received_to_date: money,
  spent_to_date: money,
  generated_at: z.string(),
  generated_by: z.string(),
});
export type UcView = z.infer<typeof ucView>;

export async function fetchView<T>(
  apiUrl: string,
  path: string,
  authorization: string,
  schema: z.ZodType<T>,
): Promise<T> {
  const res = await fetch(`${apiUrl}/api/v1${path}`, {
    headers: { Authorization: authorization, Accept: "application/json" },
  });
  const body: unknown = await res.json().catch(() => null);
  if (!res.ok) throw new UpstreamError(res.status, body);
  const view = schema.parse(body); // throws ZodError -> 500 export_failed
  const format = (body as { date_format?: unknown } | null)?.date_format;
  if (typeof format === "string") setDateFormat(format); // dates as the university writes them
  return view;
}

// ponytail: a filtered list is read whole into memory, 200 rows a request; stream the CSV if
// lists ever pass this cap.
const LIST_PAGE = 200; // within every list endpoint's own limit
const LIST_MAX_ROWS = 50_000;

/** Every row of a filtered list (/internal/lists/<name>): pages until the API's X-Total-Count
 *  is reached, so the file is never a silently cut-off page. */
export async function fetchList(apiUrl: string, name: string, query: URLSearchParams, authorization: string): Promise<TableView> {
  const rows: TableView["rows"] = [];
  for (;;) {
    const page = new URLSearchParams(query);
    page.set("limit", String(LIST_PAGE));
    page.set("offset", String(rows.length));
    const res = await fetch(`${apiUrl}/api/v1/internal/lists/${name}?${page}`, {
      headers: { Authorization: authorization, Accept: "application/json" },
    });
    const body: unknown = await res.json().catch(() => null);
    if (!res.ok) throw new UpstreamError(res.status, body);
    const view = tableView.parse(body);
    const total = Number(res.headers.get("x-total-count"));
    if (!Number.isInteger(total)) throw new Error(`list ${name}: the API sent no row total`);
    if (total > LIST_MAX_ROWS) throw new UpstreamError(422, { error: { code: "export_too_large", message: `This list has ${total} rows. Narrow it with the filters and export again.` } });
    rows.push(...view.rows);
    if (rows.length >= total || view.rows.length === 0) return { ...view, rows };
  }
}
