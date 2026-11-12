"""Every paged list as a table for the export service (UX_FLOWS "Long lists"): one route per
list under /internal/lists/<name>. Each runs the list's own endpoint function as a dependency,
so scope, search, filters, sort, paging and redaction are the page's, by construction; this
module only chooses the columns."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app import branding
from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.db import get_session
from app.enums import ModuleKey
from app.modules import require_module
from app.routers import (
    admissions,
    audit,
    conferences,
    documents,
    faculty,
    fellowships,
    meetings,
    milestones,
    projects,
    publications,
    reports,
    scholars,
    seminars,
    theses,
)

router = APIRouter(prefix="/internal/lists", tags=["internal"])

Cell = str | int | float | None
# (heading, dotted path into the row); a path ending in "~" turns stored codes into words
# (in_review -> in review).
Columns = tuple[tuple[str, str], ...]


def _text(value: Any, humanize: bool) -> Cell:
    if value is None or (isinstance(value, (int, float)) and not isinstance(value, bool)):
        return value
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return "; ".join(str(_text(v, humanize)) for v in value)
    return str(value).replace("_", " ") if humanize else str(value)


def _cell(row: dict[str, Any], path: str) -> Cell:
    value: Any = row
    for key in path.removesuffix("~").split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return _text(value, path.endswith("~"))


def _add(
    name: str, title: str, endpoint: Callable[..., Any], module: ModuleKey | None, columns: Columns
) -> None:
    async def view(
        rows: list[Any] = Depends(endpoint),
        principal: Principal = Depends(current_principal),
        session: AsyncSession = Depends(get_session),
    ) -> dict[str, Any]:
        dicts = [r.model_dump() if isinstance(r, BaseModel) else r for r in rows]
        return {
            **await branding.export_fields(session),
            "title": title,
            "columns": [heading for heading, _ in columns],
            "rows": [[_cell(d, path) for _, path in columns] for d in dicts],
            "generated_at": datetime.now(UTC),
            "generated_by": principal.full_name,
        }

    router.add_api_route(
        f"/{name}",
        view,
        methods=["GET"],
        name=f"export_{name}",
        dependencies=[Depends(require_module(module))] if module else [],
    )


SCHOLAR = (("Scholar", "scholar.name"),)
STATE = (("State", "state~"), ("Waiting on", "waiting_on"), ("Last change", "updated_at"))

_add("scholars", "Scholars", scholars.list_scholars, None, (
    ("Scholar", "full_name"), ("Roll number", "roll_number"), ("Email", "email"),
    ("Department", "unit.name"), ("Stage", "stage"), ("Supervisor", "supervisor.name"),
    ("Co-supervisor", "co_supervisor.name"), ("Research title", "research_title"),
    ("Admitted on", "admission_date"), ("Mode", "study_mode~"),
    # Blank for a reader scope.sees_personal turns away, as on the page.
    ("Gender", "gender"), ("Category", "category"), ("Person with disability", "has_disability"),
))  # fmt: skip
_add("faculty", "Faculty", faculty.list_faculty, None, (
    ("Name", "full_name"), ("Email", "email"), ("Designation", "designation"),
    ("Department", "unit.name"), ("Employee ID", "employee_id"),
    ("Can supervise", "can_supervise"), ("Scholars", "load"), ("Limit", "max_scholars"),
))  # fmt: skip
_add("milestones", "Register of decisions", milestones.list_milestones, None, (
    *SCHOLAR, ("Roll number", "roll_number"), ("Department", "unit.name"),
    ("Milestone", "milestone_type~"), ("Committee", "approval_body"),
    ("Resolution number", "resolution_number"), ("Resolution date", "resolution_date"),
    ("Decision", "status"), ("Approved title", "approved_title"), ("Notes", "notes"),
))  # fmt: skip
_add("reports", "Progress reports", reports.list_reports, None, (
    ("Year", "report_year"), ("Period", "period"), *SCHOLAR, *STATE,
    ("Submitted", "submitted_at"), ("Approved", "approved_at"),
))  # fmt: skip
_add("meetings", "Meetings", meetings.list_meetings, None, (
    ("Date", "meeting_date"), *SCHOLAR, ("Supervisor", "supervisor.name"), ("Agenda", "agenda"),
    ("Next meeting", "next_meeting_date"),
))  # fmt: skip
_add("seminars", "Progress seminars", seminars.list_seminars, None, (
    ("When", "starts_at"), ("Title", "title"), ("Department", "unit.name"), ("Venue", "venue"),
    ("Scholars", "scholar_count"), ("Report due", "report_due"), ("Status", "status"),
))  # fmt: skip
_add("publications", "Publications", publications.list_publications, "publications", (
    ("Title", "title"), *SCHOLAR, ("Type", "pub_type~"), ("Venue", "venue"), ("Year", "pub_year"),
    ("Indexed in", "indexing~"), *STATE,
))  # fmt: skip
_add("theses", "Thesis submissions", theses.list_theses, "documents", (
    ("Thesis", "title"), *SCHOLAR, *STATE,
))  # fmt: skip
_add("conferences", "Conferences and talks", conferences.list_conferences, "conferences", (
    ("Date", "event_date"), ("Event", "event_name"), ("Place", "place"), *SCHOLAR,
    ("Contribution", "event_type~"), ("Title", "title"),
))  # fmt: skip
_add("documents", "Drafts and chapters", documents.list_documents, "documents", (
    ("Document", "title"), *SCHOLAR, ("Kind", "doc_kind~"), ("Last change", "updated_at"),
))  # fmt: skip
_add("admissions", "Admissions", admissions.list_admissions, "admissions", (
    ("Candidate", "candidate_name"), ("Email", "email"), ("Phone", "phone"),
    ("Department", "unit.name"), ("Route", "entrance_route~"), ("Score", "entrance_score"),
    ("Interview", "interview_date"), ("Result", "interview_result~"),
    ("Admitted on", "admitted_on"),
))  # fmt: skip
_add("fellowships", "Fellowships", fellowships.list_fellowships, "fellowships", (
    *SCHOLAR, ("Roll number", "roll_number"), ("Department", "unit.name"), ("Scheme", "scheme~"),
    ("Per month", "amount_monthly"), ("HRA", "hra_amount"), ("From", "start_date"),
    ("To", "end_date"), ("Status", "status"),
))  # fmt: skip
_add("projects", "Research projects", projects.list_projects, "projects", (
    ("Project", "title"), ("Sanction number", "sanction_number"), ("Agency", "agency"),
    ("PI", "pi.name"), ("Department", "unit.name"), ("Sanctioned", "amount_sanctioned"),
    ("From", "start_date"), ("To", "end_date"), ("Status", "status"),
))  # fmt: skip
_add("audit-log", "Audit log", audit.read_audit_log, None, (
    ("When", "at"), ("Who", "actor"), ("Roles", "actor_roles~"), ("What", "action~"),
    ("Record", "table_name~"), ("Record ID", "record_id"), ("From", "from_state~"),
    ("To", "to_state~"), ("Fields", "fields"), ("Scholar", "scholar.name"),
))  # fmt: skip
