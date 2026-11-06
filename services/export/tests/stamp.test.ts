/** A reviewer's copy: the code reaches every page, and the API's refusals pass straight through. */
import assert from "node:assert/strict";
import type { AddressInfo } from "node:net";
import { after, before, test } from "node:test";
import { inflateSync } from "node:zlib";
import express from "express";
import { PDFDocument } from "pdf-lib";
import { createApp, loadConfig } from "../src/server.ts";
import { stampPdf } from "../src/stamp.ts";

const ID = "6f1c2a7e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const CODE = "7F3A-92C1";
const hexOf = (text: string) => Buffer.from(text).toString("hex").toUpperCase();

async function blankPdf(pages: number): Promise<Uint8Array> {
  const doc = await PDFDocument.create();
  for (let i = 0; i < pages; i++) doc.addPage([400, 600]);
  return doc.save();
}

/** Every Flate stream in the file, inflated, as text. */
function contents(pdf: Buffer): string {
  const text = pdf.toString("latin1");
  let out = "";
  for (const m of text.matchAll(/stream\r?\n([\s\S]*?)endstream/g)) {
    try {
      out += inflateSync(Buffer.from(m[1] ?? "", "latin1")).toString("latin1");
    } catch {
      out += m[1];
    }
  }
  return out;
}

let stub: ReturnType<ReturnType<typeof express>["listen"]>;
let exporter: ReturnType<ReturnType<typeof express>["listen"]>;
let base: string;
let lastDownload: unknown;

before(async () => {
  const api = express();
  stub = api.listen(0);
  const stubUrl = `http://127.0.0.1:${(stub.address() as AddressInfo).port}`;
  api.get("/api/v1/internal/reviews/:id/copy", (req, res) => {
    lastDownload = req.query.download;
    if (req.headers.authorization !== "Bearer good") {
      return res.status(403).json({ error: { code: "forbidden", message: "No.", details: {} } });
    }
    res.json({ code: CODE, file_url: `${stubUrl}/thesis`, file_name: "thesis.pdf", download: false });
  });
  api.get("/thesis", async (_req, res) => {
    res.setHeader("Content-Type", "application/pdf");
    res.send(Buffer.from(await blankPdf(2)));
  });
  exporter = createApp(loadConfig({ API_URL: stubUrl, CORS_ORIGINS: "" } as NodeJS.ProcessEnv)).listen(0);
  base = `http://127.0.0.1:${(exporter.address() as AddressInfo).port}`;
});

after(() => {
  stub.close();
  exporter.close();
});

test("the code is printed on every page, more than once", async () => {
  const stamped = await stampPdf(await blankPdf(3), CODE);
  assert.equal((await PDFDocument.load(stamped)).getPageCount(), 3);
  assert.equal(contents(stamped).split(hexOf(CODE)).length - 1, 9);
});

test("a locked or damaged PDF is refused with a clear message", async () => {
  await assert.rejects(stampPdf(Buffer.from("not a pdf"), CODE), /locked or damaged/);
});

test("a reviewer's copy comes back stamped", async () => {
  const res = await fetch(`${base}/reviews/${ID}/thesis.pdf`, { headers: { Authorization: "Bearer good" } });
  assert.equal(res.status, 200);
  assert.equal(res.headers.get("cache-control"), "no-store");
  assert.ok(contents(Buffer.from(await res.arrayBuffer())).includes(hexOf(CODE)));
  assert.equal(lastDownload, "false");
});

test("the API's refusal reaches the caller and nothing is sent", async () => {
  const res = await fetch(`${base}/reviews/${ID}/thesis.pdf?download=1`, { headers: { Authorization: "Bearer bad" } });
  assert.equal(res.status, 403);
  assert.equal(lastDownload, "true");
  assert.equal(((await res.json()) as { error: { code: string } }).error.code, "forbidden");
});
