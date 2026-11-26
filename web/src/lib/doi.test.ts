import assert from "node:assert/strict";
import { test } from "node:test";
import { doiIn, pickDoi } from "./doi.ts";

test("finds a DOI and drops trailing punctuation", () => {
  assert.equal(doiIn("Published online. DOI: 10.1016/j.jcp.2020.109876."), "10.1016/j.jcp.2020.109876");
  assert.equal(doiIn("(https://doi.org/10.1145/3292500.3330701)"), "10.1145/3292500.3330701");
  assert.equal(doiIn("https://doi.org/10.1002%2Fanie.201915678"), "10.1002/anie.201915678");
  assert.equal(doiIn("no identifier here"), null);
  assert.equal(doiIn("bad % encoding 10.1000/xyz"), "10.1000/xyz");
});

test("metadata wins, then the first page's text, then its doi.org links", () => {
  assert.equal(pickDoi(["", "doi:10.1000/meta"], "DOI 10.1000/text", []), "10.1000/meta");
  assert.equal(pickDoi([], "Received 2024. https://doi.org/10.1000/text", ["https://doi.org/10.1000/link"]), "10.1000/text");
  assert.equal(pickDoi([], "Abstract", ["https://example.org/10.1000/other", "https://doi.org/10.1000/link"]), "10.1000/link");
  assert.equal(pickDoi([], "Abstract", []), null);
});
