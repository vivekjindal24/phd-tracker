/** API read client — forwards the caller's Authorization header; the API enforces RBAC.
 * The export service holds zero auth/data logic of its own. Failures propagate loudly. */

import { z } from "zod";

export class ApiError extends Error {
	constructor(
		public status: number,
		public code: string,
		message: string,
	) {
		super(message);
	}
}

export const ReportViewSchema = z.object({
	report: z.object({
		id: z.string(),
		report_year: z.number(),
		period: z.string(),
		summary: z.string(),
		supervisor_comment: z.string().nullable(),
		approved_on: z.string().nullable(),
		state: z.string(),
		created_at: z.string(),
	}),
	scholar: z.object({
		scholar_name: z.string(),
		roll_number: z.string(),
		department: z.string(),
		admission_date: z.string(),
		stage: z.string(),
	}),
	supervisor: z.object({ full_name: z.string() }).nullable(),
});
export type ReportView = z.infer<typeof ReportViewSchema>;

export const MilestoneRowSchema = z.object({
	scholar_name: z.string(),
	roll_number: z.string(),
	department: z.string(),
	milestone_type: z.string(),
	status: z.string(),
	approval_body: z.string().nullable(),
	resolution_number: z.string().nullable(),
	resolution_date: z.string().nullable(),
	notes: z.string().nullable(),
});
export type MilestoneRow = z.infer<typeof MilestoneRowSchema>;

export async function apiGet<T>(path: string, authorization: string, schema: z.ZodType<T>): Promise<T> {
	const base = process.env.API_URL;
	if (!base) throw new ApiError(500, "misconfigured", "API_URL is not set");
	let res: Response;
	try {
		res = await fetch(`${base.replace(/\/$/, "")}${path}`, {
			headers: { authorization },
		});
	} catch (err) {
		throw new ApiError(502, "upstream_unavailable", `Cannot reach the API: ${String(err)}`);
	}
	const body: unknown = await res.json().catch(() => null);
	if (!res.ok) {
		const env = (body as { error?: { code?: string; message?: string } })?.error;
		throw new ApiError(
			res.status,
			env?.code ?? "upstream_error",
			env?.message ?? `The API responded ${res.status}`,
		);
	}
	return schema.parse(body);
}