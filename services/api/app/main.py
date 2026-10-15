"""App factory. healthz is the deploy/uptime probe; everything else is authed."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import router as auth_router
from .config import settings
from .errors import register_error_handlers
from .routers import internal, meetings, milestones, reports, scholars, search, supervisors


def create_app() -> FastAPI:
	app = FastAPI(title="PhD Tracker API", version="0.2.0")

	if settings.cors_origins:
		origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
		app.add_middleware(
			CORSMiddleware,
			allow_origins=origins,  # explicit allowlist, never "*"
			allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
			allow_headers=["Authorization", "Content-Type"],
		)

	register_error_handlers(app)

	prefix = settings.api_prefix
	app.include_router(auth_router.router, prefix=prefix)
	for router in (scholars, supervisors, meetings, reports, milestones, search, internal):
		app.include_router(router.router, prefix=prefix)

	@app.get(f"{prefix}/healthz")
	def healthz() -> dict:
		return {"status": "ok", "service": "api"}

	return app


app = create_app()