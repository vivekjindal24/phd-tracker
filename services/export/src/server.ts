import express, { type Request, type Response } from "express";

// Export service holds zero auth logic of its own: every data request forwards
// the caller's Authorization header to the API, which enforces RBAC.
export function createApp() {
	const app = express();

	app.get("/healthz", (_req: Request, res: Response) => {
		res.json({ status: "ok", service: "export" });
	});

	return app;
}

if (process.env.NODE_ENV !== "test") {
	const port = Number(process.env.PORT ?? 8100);
	createApp().listen(port, () => {
		console.log(`export service listening on :${port}`);
	});
}