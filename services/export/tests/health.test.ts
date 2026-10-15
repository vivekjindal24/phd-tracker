import assert from "node:assert/strict";
import { test } from "node:test";
import type { AddressInfo } from "node:net";
import { createApp } from "../src/server.ts";

test("healthz responds ok", async () => {
	const server = createApp().listen(0);
	const { port } = server.address() as AddressInfo;
	try {
		const res = await fetch(`http://127.0.0.1:${port}/healthz`);
		assert.equal(res.status, 200);
		assert.deepEqual(await res.json(), { status: "ok", service: "export" });
	} finally {
		server.close();
	}
});