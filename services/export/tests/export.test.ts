import assert from "node:assert/strict";
import { test } from "node:test";
import type { AddressInfo } from "node:net";
import http from "node:http";

import { createApp } from "../src/server.ts";
import { buildRegisterCsv } from "../src/register.ts";
import type { MilestoneRow, ReportView } from "../src/apiClient.ts";

const REPORT_VIEW: ReportView = {
	report: {
		id: "11111111-1111-1111-1111-111111111111",
		report_year: 2026,
		period: "January-June",
		summary: "Completed the planned experiments; two chapters revised.",
		supervisor_comment: "Good progress.",
		approved_on: "2026-07-10",
		state: "approved",
		created_at: "2026-07-01T10:00:00",
	},
	scholar: {
		scholar_name: "Arun Bhatt",
		roll_number: "PHD-CS-2024-001",
		department: "Computer Science",
		admission_date: "2024-07-01",
		stage: "Research Phase",
	},
	supervisor: { full_name: "Dr. Meera Krishnan" },
};

const MILESTONE_ROW: MilestoneRow = {
	scholar_name: "Arun Bhatt",
	roll_number: "PHD-CS-2024-001",
	department: "Computer Science",
	milestone_type: "Proposal Approval (RDC)",
	status: "Approved",
	approval_body: "RDC",
	resolution_number: "RDC/2024/031",
	resolution_date: "2024-11-22",
	notes: 'Unanimous, "noted"',
};

/** Stub of the API's /internal endpoints — same envelope, same auth-forwarding contract. */
function startStubApi(handler: (url: string, authorization: string | undefined) => { status: number; body: unknown }) {
	const server = http.createServer((req, res) => {
		const { status, body } = handler(req.url ?? "", req.headers.authorization);
		res.writeHead(status, { "content-type": "application/json" });
		res.end(JSON.stringify(body));
	});
	server.listen(0);
	const port = (server.address() as AddressInfo).port;
	return { server, url: `http://127.0.0.1:${port}` };
}

function startExport() {
	const server = createApp().listen(0);
	const port = (server.address() as AddressInfo).port;
	return { server, url: `http://127.0.0.1:${port}` };
}

const AUTH = "Bearer test-token";

test("APR pdf renders a real PDF from the API view", async () => {
	const api = startStubApi((url, auth) => {
		assert.equal(auth, AUTH, "Authorization header must be forwarded verbatim");
		assert.match(url, /^\/internal\/reports\/[\w-]+\/export-view$/);
		return { status: 200, body: REPORT_VIEW };
	});
	process.env.API_URL = api.url;
	const exp = startExport();
	try {
		const res = await fetch(`${exp.url}/export/reports/11111111-1111-1111-1111-111111111111.pdf`, {
			headers: { Authorization: AUTH },
		});
		assert.equal(res.status, 200);
		assert.equal(res.headers.get("content-type"), "application/pdf");
		const bytes = Buffer.from(await res.arrayBuffer());
		assert.ok(bytes.subarray(0, 4).toString() === "%PDF", "must be a PDF");
		assert.ok(bytes.length > 1000, "must have content");
	} finally {
		exp.server.close();
		api.server.close();
	}
});

test("register csv: rows, header, escaping", async () => {
	const api = startStubApi(() => ({ status: 200, body: [MILESTONE_ROW] }));
	process.env.API_URL = api.url;
	const exp = startExport();
	try {
		const res = await fetch(`${exp.url}/export/milestones.csv?department=CS`, { headers: { Authorization: AUTH } });
		assert.equal(res.status, 200);
		const csv = await res.text();
		const lines = csv.trimEnd().split("\n");
		assert.equal(lines.length, 2);
		assert.ok(lines[0].startsWith("Scholar,Roll number"));
		assert.ok(lines[1].includes('"Unanimous, ""noted"""'), "quotes and commas must be escaped");
	} finally {
		exp.server.close();
		api.server.close();
	}
});

test("empty register csv is the header row only", () => {
	const csv = buildRegisterCsv([]);
	assert.equal(csv, "Scholar,Roll number,Department,Milestone,Status,Approval body,Resolution no.,Resolution date,Notes\n");
});

test("empty register pdf renders a cover page, never a blank page", async () => {
	const api = startStubApi(() => ({ status: 200, body: [] }));
	process.env.API_URL = api.url;
	const exp = startExport();
	try {
		const res = await fetch(`${exp.url}/export/milestones.pdf`, { headers: { Authorization: AUTH } });
		assert.equal(res.status, 200);
		const bytes = Buffer.from(await res.arrayBuffer());
		assert.ok(bytes.subarray(0, 4).toString() === "%PDF");
		assert.ok(bytes.length > 500, "cover page must have content");
	} finally {
		exp.server.close();
		api.server.close();
	}
});

test("API 403 propagates as the same 403 envelope", async () => {
	const api = startStubApi(() => ({
		status: 403,
		body: { error: { code: "permission_denied", message: "Exports are restricted to the research office", details: null } },
	}));
	process.env.API_URL = api.url;
	const exp = startExport();
	try {
		const res = await fetch(`${exp.url}/export/reports/xyz.pdf`, { headers: { Authorization: AUTH } });
		assert.equal(res.status, 403);
		const body = (await res.json()) as { error: { code: string } };
		assert.equal(body.error.code, "permission_denied");
	} finally {
		exp.server.close();
		api.server.close();
	}
});

test("missing authorization is rejected before the API is called", async () => {
	const exp = startExport();
	try {
		const res = await fetch(`${exp.url}/export/reports/xyz.pdf`);
		assert.equal(res.status, 401);
		const body = (await res.json()) as { error: { code: string } };
		assert.equal(body.error.code, "unauthenticated");
	} finally {
		exp.server.close();
	}
});