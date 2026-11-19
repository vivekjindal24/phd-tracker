/** Export service against a stub API: token forwarding, error envelopes, CORS, CSV safety. */
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import express from "express";
import { PDFDocument as PDFLibDocument } from "pdf-lib";
import { createApp, loadConfig } from "../src/server.ts";
import { phdFileView, reportView } from "../src/api.ts";
import { certificatePdf, csvCell, phdFilePdf, reportPdf, tableCsv } from "../src/render.ts";

const REPORT_ID = "6f1c2a7e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const JUNK_ID = "00000000-0000-4000-8000-000000000000";
const report = {
  university: "Demo University", address: "", logo: null, unit: "CSE", scholar: "Arun Kumar", roll_number: "PHD-CSE-001",
  supervisor: "Meera", committee: ["Prof. R. Sen (IIT Delhi)"], period: "July-December", report_year: 2026,
  summary: "Survey finished, baselines run, chapter two drafted.",
  sections: [{ name: "Work done this period", text: "Baselines run on the district panel." }],
  activity: { meetings: 4, publications: ["A paper (accepted)"], conferences: null }, files: ["report.pdf"],
  state: "in_review",
  submitted_at: "2026-10-01T10:00:00Z", approved_at: null,
  history: [{ action: "submit", actor: "Arun Kumar", step: "Supervisor", to: null, comment: null, rating: null, at: "2026-10-01T10:00:00Z" }],
  generated_at: "2026-10-22T10:00:00Z", generated_by: "Meera",
};
const register = {
  university: "Demo University", address: "", logo: null, unit: null, filters: { milestone_type: null, status: null },
  rows: [{ scholar: "Arun Kumar", roll_number: "PHD-CSE-001", unit: "CSE", milestone_type: "viva",
    status: "Approved", approval_body: "RDC", resolution_number: "=HYPERLINK(\"x\")",
    resolution_date: "2026-09-30", notes: "Held, \"cleared\"" }],
  generated_at: "2026-10-22T10:00:00Z", generated_by: "Research Office",
};

const uc = {
  university: "Demo University", address: "", logo: null, unit: "ECE", title: "Low-power edge inference", agency: "SERB",
  sanction_number: "SERB/CRG/2025/001", amount_sanctioned: 2500000, pi: "Dr B",
  period_start: "2026-04-01", period_end: "2027-03-31", opening_balance: 800000,
  grants_received: [{ date: "2026-05-01", reference: "SERB/2nd", amount: 500000 }], received: 500000,
  available: 1300000, spent_by_head: { travel: 50000, consumables: 25000 }, spent: 75000,
  closing_balance: 1225000, received_to_date: 1500000, spent_to_date: 275000,
  generated_at: "2026-10-31T10:00:00Z", generated_by: "Research Office",
};

const certificate = {
  university: "Demo University", address: "", logo: null, unit: "Physics", serial: "DEMO/PHD/2026/1", scholar: "Kabir Malhotra",
  roll_number: "PHD-PHY-2021-003", degree: "Doctor of Philosophy", opening: "This is to certify that",
  title_lead: "has successfully defended the thesis entitled", body: "held on {viva_date}, degree of {degree}.",
  signatories: ["Controller of Examinations", "Registrar", "Vice-Chancellor"],
  thesis_title: "Topological phases in cold atoms", viva_date: "2026-10-20",
  issued_on: "2026-11-06", verify_url: "https://research.example.edu/verify/abc",
  generated_at: "2026-11-06T10:00:00Z", generated_by: "Research Office",
};

const entry = (heading: string, signed: boolean | null = null) =>
  ({ date: "2022-05-01", heading, lines: [["Result", "Satisfactory"]], signed });
const phdFile = {
  university: "U", address: "", logo: null, scholar: "Arun", roll_number: "PHD-1", unit: "CSE",
  supervisor: "Meera", admission_date: "2021-08-01",
  annexures: [
    { key: "admission", title: "Admission and entrance record", date: null, note: "Not on record", entries: [] },
    { key: "comprehensive", title: "Comprehensive examination", date: "2022-05-01", note: null,
      entries: [entry("Attempt 1"), entry("Attempt 2")] },
    { key: "progress", title: "Progress reports", date: "2022-12-01", note: null, entries: [entry("Report", false)] },
    { key: "examiners", title: "Examiners' reports", date: null, note: "Not shown to you", entries: [] },
  ],
  generated_at: "2026-11-19T10:00:00Z", generated_by: "R",
};
const pageCount = (pdf: Buffer) => (pdf.toString("latin1").match(/\/Type \/Page\b(?!s)/g) ?? []).length;

const seen: { auth?: string; url?: string } = {};
const listCalls: string[] = [];
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
    if (req.path.startsWith("/api/v1/internal/certificates/")) return res.json(certificate);
    if (req.path.endsWith("/export-view")) return res.json(req.path.includes(JUNK_ID) ? { nope: 1 } : report);
    if (req.path.endsWith("/register-view")) return res.json(register);
    if (req.path.endsWith("/phd-file")) return res.json(phdFile);
    if (req.path === "/api/v1/internal/lists/scholars") {
      // Three rows in all; the stub hands out two a page whatever limit is asked.
      const offset = Number(req.query.offset);
      listCalls.push(req.url);
      res.setHeader("X-Total-Count", "3");
      return res.json({ university: "U", address: "", logo: null, title: "Scholars", columns: ["Scholar", "Stage"],
        rows: [["Arun", "Viva"], ["Priya", "Coursework"], ["Zoya", "Registered"]].slice(offset, offset + 2),
        generated_at: "2026-11-12T10:00:00Z", generated_by: "R" });
    }
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

test("certificate PDF is rendered from the export view, with the token forwarded", async () => {
  const res = await get(`/certificates/${REPORT_ID}.pdf`);
  assert.equal(res.status, 200);
  assert.equal(seen.url, `/api/v1/internal/certificates/${REPORT_ID}/export-view`);
  assert.match(res.headers.get("content-disposition") ?? "", /provisional-certificate-PHD-PHY-2021-003\.pdf/);
  assert.equal(Buffer.from(await res.arrayBuffer()).subarray(0, 5).toString(), "%PDF-");
});

test("a broken logo is logged and never blocks the PDF", async () => {
  const res = await certificatePdf({ ...certificate, address: "Sector 1", logo: Buffer.from("not an image").toString("base64") });
  assert.equal(res.subarray(0, 5).toString(), "%PDF-");
});

const DOT_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

test("signed steps carry the signature; a broken one never blocks the PDF", async () => {
  const signed = { action: "approve", actor: "Meera", step: "Supervisor", to: null, comment: null, rating: null, at: "2026-10-02T10:00:00Z" };
  const res = await reportPdf(reportView.parse({
    ...report,
    history: [
      ...report.history,
      { ...signed, signature: `data:image/png;base64,${DOT_PNG}` },
      { ...signed, signature: "data:image/png;base64,bm90IGFuIGltYWdl" },
    ],
  }));
  assert.equal(res.subarray(0, 5).toString(), "%PDF-");
});

test("the unsigned copy leaves the signatures out, for signing the print by hand", async () => {
  const view = reportView.parse({ ...report, history: [...report.history, { action: "approve", actor: "Meera",
    step: "Supervisor", to: null, comment: null, rating: null, at: "2026-10-02T10:00:00Z",
    signature: `data:image/png;base64,${DOT_PNG}` }] });
  const image = /\/Subtype \/Image/;
  assert.match((await reportPdf(view)).toString("latin1"), image);
  assert.doesNotMatch((await reportPdf(view, false)).toString("latin1"), image);
  const res = await get(`/reports/${REPORT_ID}.pdf?signed=0`);
  assert.match(res.headers.get("content-disposition") ?? "", /-2026-unsigned\.pdf/);
  assert.equal((await get(`/reports/${REPORT_ID}.pdf?signed=maybe`)).status, 422);
});

test("the assistantship line parses and renders; an old view without it still does", async () => {
  for (const view of [{ ...report, assistantship: "without" }, report]) {
    const res = await reportPdf(reportView.parse(view));
    assert.equal(res.subarray(0, 5).toString(), "%PDF-");
  }
  assert.throws(() => reportView.parse({ ...report, assistantship: "maybe" }));
});

test("the PhD file: the index page, then one page per recorded annexure", async () => {
  const res = await get(`/scholars/${REPORT_ID}/phd-file.pdf`);
  assert.equal(res.status, 200);
  assert.equal(seen.url, `/api/v1/internal/scholars/${REPORT_ID}/phd-file`);
  assert.match(res.headers.get("content-disposition") ?? "", /phd-file-PHD-1\.pdf/);
  const pdf = Buffer.from(await res.arrayBuffer());
  assert.equal(pageCount(pdf), 3); // index + two annexures with entries; the empty two are only listed
  assert.equal(pageCount(await phdFilePdf(phdFileView.parse({ ...phdFile, annexures: [] }))), 1);
});

test("approved papers stand after their entry, in order: a PDF's pages, a photo, a note for a bad one", async () => {
  const two = await PDFLibDocument.create();
  two.addPage([300, 400]).drawText("Signed: Dr. Meera", { x: 20, y: 200 });
  two.addPage([300, 400]); // blank: cannot be embedded, so the page carries a note instead
  const copy = (id: string, content_type: string) =>
    ({ label: "Report", copy: { id, content_type, scan_url: `https://bucket/${id}` } });
  const view = phdFileView.parse({ ...phdFile, annexures: [{ key: "progress", title: "Progress", date: null, note: null,
    entries: [
      { ...entry("Seminar 1", true), papers: [copy("a", "application/pdf"), copy("b", "image/png")] },
      { ...entry("Report 3", true), papers: [copy("c", "application/pdf")] }, // not fetched
      { ...entry("Report 4"), papers: [{ label: "Report", copy: { id: "d", content_type: "image/png", scan_url: null } },
        { label: "Attendance sheet", copy: null }] }, // waiting; not uploaded
    ] }] });
  const scans = new Map([
    ["a", { bytes: await two.save(), type: "application/pdf" }],
    ["b", { bytes: Buffer.from(DOT_PNG, "base64"), type: "image/png" }],
  ]);
  const pdf = await phdFilePdf(view, scans);
  // index + the annexure page + two scanned pages + the photo + a note for the one not fetched
  assert.equal((await PDFLibDocument.load(pdf)).getPageCount(), 6);
});

test("NAAC CSV keeps numbers and neutralises formulas", () => {
  const csv = tableCsv({ university: "U", address: "", logo: null, title: "T", columns: ["Title", "Amount", "Note"],
    rows: [["=cmd()", 40000, null]], generated_at: "2026-11-06T10:00:00Z", generated_by: "R" });
  assert.equal(csv, "\uFEFFTitle,Amount,Note\r\n'=cmd(),40000,\r\n");
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

test("a list export pages to the total and forwards the page's filters and sort", async () => {
  const res = await get("/lists/scholars.csv?q=a&sort=-stage&limit=1&offset=9");
  assert.equal(res.status, 200);
  assert.match(res.headers.get("content-disposition") ?? "", /scholars\.csv/);
  // (fetch's text() drops the BOM the file starts with)
  assert.equal(await res.text(), "Scholar,Stage\r\nArun,Viva\r\nPriya,Coursework\r\nZoya,Registered\r\n");
  assert.deepEqual(listCalls, [
    "/api/v1/internal/lists/scholars?q=a&sort=-stage&limit=200&offset=0",
    "/api/v1/internal/lists/scholars?q=a&sort=-stage&limit=200&offset=2",
  ]);
});

test("a list export refuses unknown lists and odd query keys", async () => {
  assert.equal((await get("/lists/passwords.csv")).status, 422);
  assert.equal((await get("/lists/scholars.csv?Bad-Key=1")).status, 422);
});
