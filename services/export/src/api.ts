/** Reads from the API's /internal endpoints with the caller's token forwarded verbatim.
 *  Every response is validated with zod: a malformed upstream is a loud 500, never a
 *  silently blank PDF (CODE_STYLE.md §3). */
import { z } from "zod";

export class UpstreamError extends Error {
  constructor(
    public status: number,
    public body: unknown,
  ) {
    super(`API answered ${status}`);
  }
}

const historyEntry = z.object({
  action: z.string(),
  actor: z.string(),
  step: z.string().nullable(),
  to: z.string().nullable(),
  comment: z.string().nullable(),
  at: z.string(),
});

export const reportView = z.object({
  university: z.string(),
  unit: z.string().nullable(),
  scholar: z.string(),
  roll_number: z.string(),
  supervisor: z.string().nullable(),
  period: z.string(),
  report_year: z.number().int(),
  summary: z.string(),
  state: z.enum(["draft", "in_review", "sent_back", "approved"]),
  submitted_at: z.string().nullable(),
  approved_at: z.string().nullable(),
  history: z.array(historyEntry),
  generated_at: z.string(),
  generated_by: z.string(),
});
export type ReportView = z.infer<typeof reportView>;

export const registerView = z.object({
  university: z.string(),
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
  return schema.parse(body); // throws ZodError -> 500 export_failed
}
