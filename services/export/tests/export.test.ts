/** Export service against a stub API: token forwarding, error envelopes, CORS, CSV safety. */
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import express from "express";
import { createApp, loadConfig } from "../src/server.ts";
import { csvCell } from "../src/render.ts";

const REPORT_ID = "6f1c2a7e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const JUNK_ID = "00000000-0000-4000-8000-000000000000";
const report = {
  university: "Demo University", unit: "CSE", scholar: "Arun Kumar", roll_number: "PHD-CSE-001",
  supervisor: "Meera", period: "July-December", report_year: 2026,
  summary: "Survey finished, baselines run, chapter two drafted.", state: "in_review",
  submitted_at: "2026-10-01T10:00:00Z", approved_at: null,
  history: [{ action: "submit", actor: "Arun Kumar", step: "Supervisor", to: null, comment: null, at: "2026-10-01T10:00:00Z" }],
  generated_at: "2026-10-22T10:00:00Z", generated_by: "Meera",
};
const register = {
  university: "Demo University", unit: null, filters: { milestone_type: null, status: null },
  rows: [{ scholar: "Arun Kumar", roll_number: "PHD-CSE-001", unit: "CSE", milestone_type: "viva",
    status: "Approved", approval_body: "RDC", resolution_number: "=HYPERLINK(\"x\")",
    resolution_date: "2026-09-30", notes: "Held, \"cleared\"" }],
  generated_at: "2026-10-22T10:00:00Z", generated_by: "Research Office",
};

const uc = {
  university: "Demo University", unit: "ECE", title: "Low-power edge inference", agency: "SERB",
  sanction_number: "SERB/CRG/2025/001", amount_sanctioned: 2500000, pi: "Dr B",
  period_start: "2026-04-01", period_end: "2027-03-31", opening_balance: 800000,
  grants_received: [{ date: "2026-05-01", reference: "SERB/2nd", amount: 500000 }], received: 500000,
  available: 1300000, spent_by_head: { travel: 50000, consumables: 25000 }, spent: 75000,
  closing_balance: 1225000, received_to_date: 1500000, spent_to_date: 275000,
  generated_at: "2026-10-31T10:00:00Z", generated_by: "Research Office",
};

const seen: { auth?: string; url?: string } = {};
let stubUrl = "";
let exportUrl = "";
const servers: { close: () => void }[] = [];

before(async () => {
  const stub = express();
  stub.use((req, res) => {
    seen.auth = req.headers.authorization;
    seen.url = req.url;
    if (req.headers.authorization !== "Bearer good") return res.status(403).json({ error: { code: "forbidden", message: "Not yours." } });
    if (req.path.startsWith("/api/v1/internal/ucs/")) return res.json(uc);
    if (req.path.endsWith("/export-view")) return res.json(req.path.includes(JUNK_ID) ? { nope: 1 } : report);
    if (req.path.endsWith("/register-view")) return res.json(register);
    res.sendStatus(404);
  });
  const listen = (app: express.Express) =>
    new Promise<string>((resolve) => {
      const s = app.listen(0, () => resolve(`http://127.0.0.1:${(s.address() as AddressInfo).port}`));
      servers.push(s);
    });
  stubUrl = await listen(stub);
  exportUrl = await listen(createApp({ apiUrl: stubUrl, corsOrigins: ["https://research.example.edu"] }));
});
after(() => servers.forEach((s) => s.close()));

const get = (path: string, auth = "Bearer good", headers: Record<string, string> = {}) =>
  fetch(`${exportUrl}${path}`, { headers: { Authorization: auth, ...headers } });

test("report PDF forwards the caller's token and returns a PDF", async () => {
  const res = await get(`/reports/${REPORT_ID}.pdf`);
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("content-type"), "application/pdf");
  assert.match(res.headers.get("content-disposition") ?? "", /progress-report-PHD-CSE-001-July-December-2026\.pdf/);
  assert.equal((await res.text()).slice(0, 5), "%PDF-");
  assert.equal(seen.auth, "Bearer good");
  assert.equal(seen.url, `/api/v1/internal/reports/${REPORT_ID}/export-view`);
});

test("upstream refusal passes through in the uniform envelope", async () => {
  const res = await get(`/reports/${REPORT_ID}.pdf`, "Bearer other");
  assert.equal(res.status, 403);
  assert.deepEqual(await res.json(), { error: { code: "forbidden", message: "Not yours.", details: {} } });
});

test("missing token is 401 without calling the API", async () => {
  seen.url = undefined;
  const res = await get(`/reports/${REPORT_ID}.pdf`, "");
  assert.equal(res.status, 401);
  assert.equal(seen.url, undefined);
});

test("bad input is 422, malformed upstream is 500", async () => {
  assert.equal((await get("/reports/not-a-uuid.pdf")).status, 422);
  assert.equal((await get("/register.csv?status=Maybe")).status, 422);
  const broken = await get(`/reports/${JUNK_ID}.pdf`);
  assert.equal(broken.status, 500);
  assert.equal((await broken.json()).error.code, "export_failed");
});

test("register CSV is formula-safe and filters are forwarded", async () => {
  const res = await get("/register.csv?milestone_type=viva&status=Approved");
  assert.equal(res.status, 200);
  assert.equal(seen.url, "/api/v1/internal/register-view?milestone_type=viva&status=Approved");
  const bytes = Buffer.from(await res.arrayBuffer()); // res.text() would strip the BOM
  assert.deepEqual([...bytes.subarray(0, 3)], [0xef, 0xbb, 0xbf]);
  const text = bytes.toString("utf8");
  assert.ok(text.includes("Scholar,Roll number"));
  assert.match(text, /"'=HYPERLINK\(""x""\)"/);
  assert.match(text, /"Held, ""cleared"""/);
});

test("register PDF renders", async () => {
  const res = await get("/register.pdf");
  assert.equal(res.status, 200);
  assert.equal((await res.text()).slice(0, 5), "%PDF-");
});

test("utilisation certificate PDF renders from the UC view", async () => {
  const res = await get(`/ucs/${REPORT_ID}.pdf`);
  assert.equal(res.status, 200);
  assert.equal(seen.url, `/api/v1/internal/ucs/${REPORT_ID}/export-view`);
  assert.match(res.headers.get("content-disposition") ?? "", /utilisation-certificate-SERB_CRG_2025_001-2027-03-31\.pdf/);
  assert.equal((await res.text()).slice(0, 5), "%PDF-");
});

test("CORS only answers allowlisted origins", async () => {
  const ok = await fetch(`${exportUrl}/register.pdf`, { method: "OPTIONS", headers: { Origin: "https://research.example.edu" } });
  assert.equal(ok.status, 204);
  assert.equal(ok.headers.get("access-control-allow-origin"), "https://research.example.edu");
  const bad = await fetch(`${exportUrl}/register.pdf`, { method: "OPTIONS", headers: { Origin: "https://evil.example" } });
  assert.equal(bad.status, 400);
  assert.equal(bad.headers.get("access-control-allow-origin"), null);
});

test("csvCell neutralises every formula lead character", () => {
  for (const lead of ["=", "+", "-", "@", "\t", "\r"]) assert.ok(csvCell(`${lead}1`).replace(/^"/, "").startsWith("'"));
  assert.equal(csvCell(null), "");
  assert.equal(csvCell("plain"), "plain");
});

test("config refuses a wildcard origin and a missing API URL", () => {
  assert.throws(() => loadConfig({ API_URL: "" }), /API_URL/);
  assert.throws(() => loadConfig({ API_URL: "http://x", CORS_ORIGINS: "*" }), /allowlist/);
  assert.deepEqual(loadConfig({ API_URL: "http://x/", CORS_ORIGINS: "https://a/, https://b" }),
    { apiUrl: "http://x", corsOrigins: ["https://a", "https://b"] });
});
