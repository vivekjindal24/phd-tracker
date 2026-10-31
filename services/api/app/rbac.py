"""The permission matrix as data (SECURITY.md §3). Scope (which rows) lives in scope.py;
this file only answers "may this role do this action on this entity at all"."""

from fastapi import Depends

from app.auth.deps import current_principal
from app.auth.principal import Principal
from app.errors import ApiError

R, C, U, D = "read", "create", "update", "delete"
ALL_ROLES = (
    "scholar",
    "supervisor",
    "unit_head",
    "admin",
    "research_office",
    "exam_office",
    "library",
)

# entity -> role -> allowed actions. Rows are added together with their feature.
MATRIX: dict[str, dict[str, frozenset[str]]] = {
    "org_units": {role: frozenset({R}) for role in ALL_ROLES},
    "faculty": {
        **{role: frozenset({R}) for role in ALL_ROLES},
        "admin": frozenset({R, C, U, D}),
    },
    "scholars": {
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D, "assign_supervisor"}),
        "research_office": frozenset({R}),
        "exam_office": frozenset({R}),
        "library": frozenset({R}),
    },
    "meetings": {
        "scholar": frozenset({R, C, U}),
        "supervisor": frozenset({R, C, U}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
    },
    "milestones": {
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D}),
        "research_office": frozenset({R, C, U, D}),
        "exam_office": frozenset({R}),
    },
    "progress_reports": {
        "scholar": frozenset({R, C, U}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
    },
    "todos": {
        "scholar": frozenset({R, U}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
    },
    "publications": {
        "scholar": frozenset({R, C, U}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "library": frozenset({R}),
    },
    "conferences": {
        "scholar": frozenset({R, C, U, D}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "library": frozenset({R}),
    },
    "documents": {  # drafts: the scholar and their supervisor(s) only (PRD M3)
        "scholar": frozenset({R, C, U}),
        "supervisor": frozenset({R}),
    },
    "thesis_submissions": {
        "scholar": frozenset({R, C, U}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "exam_office": frozenset({R}),
        "library": frozenset({R}),
    },
    "courses": {
        **{role: frozenset({R}) for role in ALL_ROLES},
        "admin": frozenset({R, C, U, D}),  # in their subtree
        "exam_office": frozenset({R, C, U, D}),
    },
    "enrolments": {
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "exam_office": frozenset({R, C, U, D}),
    },
    "no_dues_clearances": {  # every chain office reads; the scholar starts their own
        "scholar": frozenset({R, C}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "exam_office": frozenset({R}),
        "library": frozenset({R}),
    },
    "coursework_clearances": {
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
        "exam_office": frozenset({R, C}),
    },
    "admissions": {  # writes: admins over the unit, or the research office anywhere
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D, "convert"}),
        "research_office": frozenset({R, C, U, D, "convert"}),
    },
    "time_adjustments": {  # writes: admins over the scholar's unit, or the research office
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, D}),
        "research_office": frozenset({R, C, D}),
    },
    # Grants (PRD M6-M8). "supervisor" here means the PI: any faculty member reads their own
    # projects and adds expenses to them (scope.project_predicate, grants.py), even without
    # supervision rights — so project and ledger reads are gated by scope, not this row.
    "fellowships": {
        "scholar": frozenset({R}),
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D}),  # over the scholar's unit
        "research_office": frozenset({R, C, U, D}),
    },
    "projects": {
        "scholar": frozenset({R}),  # projects they are a member of
        "supervisor": frozenset({R}),
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D}),  # over the project's unit
        "research_office": frozenset({R, C, U, D}),
    },
    "ledger": {
        "supervisor": frozenset({R, C}),  # expenses on their own projects only
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D}),
        "research_office": frozenset({R, C, U, D}),
    },
    "leadership": {
        "unit_head": frozenset({R}),
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
    },
    "users": {
        "unit_head": frozenset({R}),
        "admin": frozenset({R, C, U, D, "manage_roles"}),
        "research_office": frozenset({R}),
    },
    "bulk_import": {"admin": frozenset({C})},  # rows still checked against the admin's subtree
    "audit_log": {
        "admin": frozenset({R}),
        "research_office": frozenset({R}),
    },
}


def roles_allowed(entity: str, action: str) -> frozenset[str]:
    return frozenset(role for role, acts in MATRIX[entity].items() if action in acts)


def can(principal: Principal, entity: str, action: str) -> bool:
    return bool(principal.roles & roles_allowed(entity, action))


def require_perm(entity: str, action: str):
    """Route guard: the caller holds at least one role allowed this action on the entity."""

    def guard(principal: Principal = Depends(current_principal)) -> Principal:
        if not can(principal, entity, action):
            raise ApiError(403, "forbidden", "You do not have permission to do this.")
        return principal

    return guard
