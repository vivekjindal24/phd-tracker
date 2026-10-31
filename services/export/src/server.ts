/** Stateless export service (ARCHITECTURE.md §2): no tables, no credentials of its own.
 *  It forwards the caller's bearer token to the API and renders what comes back. */
import express from "express";
import type { NextFunction, Request, Response } from "express";
import { z } from "zod";
import { fetchView, registerView, reportView, ucView, UpstreamError } from "./api.ts";
import { registerCsv, registerPdf, reportPdf, ucPdf } from "./render.ts";

export type Config = { apiUrl: string; corsOrigins: string[] };

export function loadConfig(env: NodeJS.ProcessEnv = process.env): Config {
  const apiUrl = (env.API_URL ?? "").trim().replace(/\/$/, "");
  if (!/^https?:\/\//.test(apiUrl)) throw new Error("API_URL must be set to the API's http(s) base URL");
  const corsOrigins = (env.CORS_ORIGINS ?? "").split(",").map((o) => o.trim().replace(/\/$/, "")).filter(Boolean);
  if (corsOrigins.includes("*")) throw new Error("CORS_ORIGINS must be an explicit allowlist, never '*'");
  return { apiUrl, corsOrigins };
}

const envelope = (res: Response, status: number, code: string, message: string) =>
  res.status(status).json({ error: { code, message, details: {} } });

class BadRequest extends Error {}
/** Request input is the caller's mistake (422); a zod failure on the API's reply is ours (500). */
function input<T>(schema: z.ZodType<T>, value: unknown): T {
  const r = schema.safeParse(value);
  if (!r.success) throw new BadRequest(r.error.issues.map((i) => i.message).join("; "));
  return r.data;
}

const registerQuery = z.object({
  unit_id: z.string().uuid().optional(),
  milestone_type: z.enum(["coursework", "proposal_approval", "rac_review", "pre_synopsis",
    "thesis_submission", "viva", "degree_awarded"]).optional(),
  status: z.enum(["Pending", "Approved", "Rejected"]).optional(),
});

export function createApp(config: Config) {
  const app = express();
  app.disable("x-powered-by");

  app.use((req, res, next) => {
    const origin = req.headers.origin;
    if (origin && config.corsOrigins.includes(origin)) {
      res.setHeader("Access-Control-Allow-Origin", origin);
      res.setHeader("Vary", "Origin");
      res.setHeader("Access-Control-Allow-Headers", "Authorization");
      res.setHeader("Access-Control-Allow-Methods", "GET");
      res.setHeader("Access-Control-Expose-Headers", "Content-Disposition");
    }
    if (req.method === "OPTIONS") return res.sendStatus(origin && config.corsOrigins.includes(origin) ? 204 : 400);
    next();
  });

  app.get("/healthz", (_req, res) => res.json({ status: "ok" }));

  const auth = (req: Request): string => {
    const header = req.headers.authorization ?? "";
    if (!header.startsWith("Bearer ")) throw new UpstreamError(401, null);
    return header;
  };
  const send = (res: Response, type: string, name: string, body: Buffer | string) => {
    res.setHeader("Content-Type", type);
    res.setHeader("Content-Disposition", `attachment; filename="${name.replace(/[^\w.-]/g, "_")}"`);
    res.setHeader("Cache-Control", "no-store");
    res.send(body);
  };

  app.get("/reports/:id.pdf", async (req, res, next) => {
    try {
      const id = input(z.string().uuid(), req.params.id);
      const view = await fetchView(config.apiUrl, `/internal/reports/${id}/export-view`, auth(req), reportView);
      send(res, "application/pdf", `progress-report-${view.roll_number}-${view.period}-${view.report_year}.pdf`,
        await reportPdf(view));
    } catch (e) {
      next(e);
    }
  });

  app.get("/ucs/:id.pdf", async (req, res, next) => {
    try {
      const id = input(z.string().uuid(), req.params.id);
      const view = await fetchView(config.apiUrl, `/internal/ucs/${id}/export-view`, auth(req), ucView);
      send(res, "application/pdf", `utilisation-certificate-${view.sanction_number}-${view.period_end}.pdf`,
        await ucPdf(view));
    } catch (e) {
      next(e);
    }
  });

  const register = async (req: Request) => {
    const q = input(registerQuery, req.query);
    const params = new URLSearchParams(Object.entries(q).filter(([, v]) => v) as [string, string][]);
    return fetchView(config.apiUrl, `/internal/register-view?${params}`, auth(req), registerView);
  };
  app.get("/register.pdf", async (req, res, next) => {
    try {
      send(res, "application/pdf", "rdc-register.pdf", await registerPdf(await register(req)));
    } catch (e) {
      next(e);
    }
  });
  app.get("/register.csv", async (req, res, next) => {
    try {
      send(res, "text/csv; charset=utf-8", "rdc-register.csv", registerCsv(await register(req)));
    } catch (e) {
      next(e);
    }
  });

  // Fail loudly with the uniform envelope; never a blank or partial document.
  app.use((err: unknown, req: Request, res: Response, _next: NextFunction) => {
    if (err instanceof UpstreamError) {
      if (err.status === 401) return envelope(res, 401, "unauthorized", "Please log in again.");
      const body = err.body as { error?: { code?: string; message?: string } } | null;
      return envelope(res, err.status, body?.error?.code ?? "upstream_error", body?.error?.message ?? "The API refused this export.");
    }
    if (err instanceof BadRequest) return envelope(res, 422, "validation_error", err.message);
    console.error(`export failed for ${req.method} ${req.path}:`, err);
    return envelope(res, 500, "export_failed", "The export could not be produced. Please try again.");
  });
  return app;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const config = loadConfig();
  const port = Number(process.env.PORT ?? 8902);
  createApp(config).listen(port, () => console.log(`export service on :${port}; API ${config.apiUrl}`));
}
