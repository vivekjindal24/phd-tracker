/** Export service routes. Stateless by construction: every request forwards the
 * caller's Authorization header to the API and renders what comes back. */

import express, { type Request, type Response } from "express";

import { ApiError, MilestoneRowSchema, ReportViewSchema, apiGet } from "./apiClient.ts";
import { buildAprPdf } from "./apr.ts";
import { buildRegisterCsv, buildRegisterPdf } from "./register.ts";

const ERROR_BODY = (status: number, code: string, message: string) => ({
	error: { code, message, details: null },
});

export function createApp() {
	const app = express();

	// Browser PDF/CSV downloads are cross-origin (Vercel web → Render export).
	// Explicit allowlist from env, never "*" — mirrors the API's CORS policy.
	const origins = (process.env.CORS_ORIGINS ?? "")
		.split(",")
		.map((o) => o.trim())
		.filter(Boolean);
	if (origins.length > 0) {
		app.use((req, res, next) => {
			const origin = req.header("origin");
			if (origin && origins.includes(origin)) {
				res.setHeader("Access-Control-Allow-Origin", origin);
				res.setHeader("Vary", "Origin");
				if (req.method === "OPTIONS") {
					// preflight for the forwarded Authorization header
					res.setHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
					res.setHeader("Access-Control-Allow-Headers", "Authorization");
					res.status(204).end();
					return;
				}
			}
			next();
		});
	}

	app.get("/healthz", (_req: Request, res: Response) => {
		res.json({ status: "ok", service: "export" });
	});

	app.get("/export/reports/:id.pdf", async (req: Request, res: Response) => {
		const authorization = req.header("authorization");
		if (!authorization) {
			res.status(401).json(ERROR_BODY(401, "unauthenticated", "Missing bearer token"));
			return;
		}
		try {
			const view = await apiGet(`/internal/reports/${req.params.id}/export-view`, authorization, ReportViewSchema);
			const pdf = await buildAprPdf(view);
			res.type("application/pdf").attachment(`APR-${req.params.id}.pdf`).send(pdf);
		} catch (err) {
			sendError(res, err);
		}
	});

	app.get("/export/milestones.pdf", async (req: Request, res: Response) => {
		await renderRegister(req, res, "pdf");
	});

	app.get("/export/milestones.csv", async (req: Request, res: Response) => {
		await renderRegister(req, res, "csv");
	});

	return app;
}

async function renderRegister(req: Request, res: Response, format: "pdf" | "csv"): Promise<void> {
	const authorization = req.header("authorization");
	if (!authorization) {
		res.status(401).json(ERROR_BODY(401, "unauthenticated", "Missing bearer token"));
		return;
	}
	try {
		const rows = await apiGet(buildInternalMilestonesPath(req), authorization, MilestoneRowSchema.array());
		if (format === "csv") {
			res.type("text/csv").attachment("milestone-register.csv").send(buildRegisterCsv(rows));
			return;
		}
		const pdf = await buildRegisterPdf(rows);
		res.type("application/pdf").attachment("milestone-register.pdf").send(pdf);
	} catch (err) {
		sendError(res, err);
	}
}

function buildInternalMilestonesPath(req: Request): string {
	const params = new URLSearchParams();
	for (const key of ["scholar_id", "department"] as const) {
		const value = req.query[key];
		if (typeof value === "string" && value !== "") params.set(key, value);
	}
	const qs = params.toString();
	return `/internal/milestones${qs ? `?${qs}` : ""}`;
}

function sendError(res: Response, err: unknown): void {
	if (err instanceof ApiError) {
		res.status(err.status).json(ERROR_BODY(err.status, err.code, err.message));
		return;
	}
	// zod parse failures and anything else: loud 500, never a silent blank PDF
	console.error("export failure:", err);
	res.status(500).json(ERROR_BODY(500, "export_failed", "The export failed to render"));
}

if (process.env.NODE_ENV !== "test") {
	const port = Number(process.env.PORT ?? 8100);
	createApp().listen(port, () => {
		console.log(`export service listening on :${port}`);
	});
}