"""One error envelope everywhere: {"error": {code, message, details}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("anveshan")

# Postgres constraint name -> (status, code, message). Named 409s, never a raw DB error.
CONSTRAINT_ERRORS: dict[str, tuple[int, str, str]] = {
    "uq_users_email": (409, "duplicate_email", "A user with this email already exists."),
    "uq_scholars_roll_number": (409, "duplicate_roll_number", "Roll number already in use."),
    "uq_org_units_code": (409, "duplicate_unit_code", "A unit with this code already exists."),
    "uq_org_root": (409, "root_exists", "The university already has a root unit."),
    "uq_org_units_path": (
        409,
        "duplicate_unit_code",
        "A sibling unit already uses an equivalent code.",
    ),
    "uq_role_assignment_active": (409, "duplicate_role", "This role is already assigned."),
    "uq_faculty_user": (409, "duplicate_profile", "This user already has a faculty profile."),
    "uq_scholars_user": (409, "duplicate_profile", "This user already has a scholar profile."),
}


class ApiError(Exception):
    def __init__(
        self, status: int, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def envelope(status: int, code: str, message: str, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def forbidden() -> ApiError:
    return ApiError(403, "forbidden", "You do not have access to this record.")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return envelope(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return envelope(422, "validation_error", "Some fields are invalid.", {"errors": errors})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        return envelope(exc.status_code, code, str(exc.detail))

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, exc: IntegrityError) -> JSONResponse:
        name = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if name in CONSTRAINT_ERRORS:
            status, code, message = CONSTRAINT_ERRORS[name]
            return envelope(status, code, message)
        log.exception("unmapped integrity error (constraint=%s)", name)
        return envelope(409, "conflict", "This change conflicts with existing data.")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", exc_info=exc)
        return envelope(500, "internal_error", "Something went wrong on our side.")
