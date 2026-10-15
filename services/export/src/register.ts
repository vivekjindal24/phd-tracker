/** Milestone register — committee export per scholar/department; PDF and CSV. */

import { docTitle, emptyState, finish, newDoc, table } from "./layout.ts";
import type { MilestoneRow } from "./apiClient.ts";

const HEADERS = [
	"Scholar", "Roll number", "Department", "Milestone", "Status",
	"Approval body", "Resolution no.", "Resolution date", "Notes",
];
const WIDTHS = [90, 90, 70, 110, 55, 60, 60, 60, 80];

export async function buildRegisterPdf(rows: MilestoneRow[]): Promise<Buffer> {
	const doc = newDoc({ landscape: true });
	if (rows.length === 0) {
		emptyState(doc, "Milestone Register");
		return finish(doc);
	}
	docTitle(doc, "Milestone Register", `${rows.length} committee approval${rows.length === 1 ? "" : "s"}`);
	table(
		doc,
		HEADERS,
		WIDTHS,
		rows.map((r) => [
			r.scholar_name, r.roll_number, r.department, r.milestone_type, r.status,
			r.approval_body, r.resolution_number, r.resolution_date, r.notes,
		]),
	);
	return finish(doc);
}

export function buildRegisterCsv(rows: MilestoneRow[]): string {
	const escape = (value: string | null): string => {
		const v = value ?? "";
		return /[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
	};
	const lines = [
		HEADERS.join(","),
		...rows.map((r) =>
			[
				r.scholar_name, r.roll_number, r.department, r.milestone_type, r.status,
				r.approval_body, r.resolution_number, r.resolution_date, r.notes,
			].map(escape).join(","),
		),
	];
	return lines.join("\n") + "\n";
}