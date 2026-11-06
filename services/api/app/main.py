import logging

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.errors import install_error_handlers
from app.routers import (
    admissions,
    auth,
    branding,
    comments,
    conferences,
    coursework,
    cron,
    dashboard,
    documents,
    duration,
    explore,
    faculty,
    faculty_requests,
    fellowships,
    files,
    grading,
    imports,
    internal,
    items,
    leadership,
    ledger,
    meetings,
    milestones,
    notifications,
    org_units,
    projects,
    publications,
    reports,
    reviews,
    scholars,
    seminars,
    theses,
    users,
    verify,
)
from app.routers import settings as settings_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

app = FastAPI(title="Anveshan API", version="0.1.0")
logging.getLogger("anveshan").info("CORS allowed origins: %s", list(settings.cors_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,  # bearer tokens, no cookies
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
install_error_handlers(app)

api = APIRouter(prefix="/api/v1")


@api.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


for module in (
    auth,
    branding,
    org_units,
    users,
    scholars,
    faculty,
    faculty_requests,
    meetings,
    reports,
    items,
    milestones,
    seminars,
    grading,
    dashboard,
    comments,
    explore,
    internal,
    settings_router,
    notifications,
    files,
    imports,
    publications,
    conferences,
    documents,
    theses,
    reviews,
    verify,
    coursework,
    admissions,
    duration,
    leadership,
    fellowships,
    projects,
    ledger,
    cron,
):
    api.include_router(module.router)
app.include_router(api)
