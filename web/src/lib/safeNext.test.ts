import assert from "node:assert/strict";
import { test } from "node:test";
import { safeNext } from "./safeNext.ts";

test("keeps a path on this site", () => {
  assert.equal(safeNext("/scholars/1?tab=x"), "/scholars/1?tab=x");
});

test("sends everything else home", () => {
  for (const bad of [null, "", "//evil.com", "/\\evil.com", "/\t/evil.com", "https://evil.com", "javascript:alert(1)"]) {
    assert.equal(safeNext(bad), "/home", String(bad));
  }
});
