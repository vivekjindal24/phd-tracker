import logging

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app import dates
from app.config import settings
from app.db import get_session
from app.errors import install_error_handlers
from app.routers import (
    admissions,
    announcements,
    audit,
    auth,
    branding,
    comments,
    committee,
    comprehensive,
    conferences,
    coursework,
    cron,
    dashboard,
    documents,
    duration,
    ethics,
    explore,
    faculty,
    faculty_publications,
    faculty_requests,
    fellowship_claims,
    fellowships,
    files,
    grading,
    grievances,
    imports,
    internal,
    items,
    leadership,
    ledger,
    list_exports,
    meetings,
    milestones,
    notifications,
    org_units,
    patents,
    projects,
    publications,
    reports,
    reviews,
    scholars,
    seminars,
    signatures,
    signed_copies,
    supervisor_changes,
    theses,
    users,
    verify,
    viva_arrangements,
)
from app.routers import settings as settings_router
from app.sorting import TOTAL_HEADER

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


async def _date_format(session: AsyncSession = Depends(get_session)) -> None:
    """Every request writes dates as the university chose (dates.py)."""
    await dates.refresh(session)


app = FastAPI(title="Anveshan API", version="0.1.0", dependencies=[Depends(_date_format)])
logging.getLogger("anveshan").info("CORS allowed origins: %s", list(settings.cors_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,  # bearer tokens, no cookies
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=[TOTAL_HEADER],  # the web reads list totals cross-origin
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
    list_exports,
    settings_router,
    signatures,
    signed_copies,
    notifications,
    files,
    imports,
    publications,
    faculty_publications,
    patents,
    conferences,
    documents,
    theses,
    viva_arrangements,
    supervisor_changes,
    reviews,
    verify,
    coursework,
    admissions,
    announcements,
    grievances,
    duration,
    committee,
    comprehensive,
    ethics,
    audit,
    leadership,
    fellowships,
    fellowship_claims,
    projects,
    ledger,
    cron,
):
    api.include_router(module.router)
app.include_router(api)
