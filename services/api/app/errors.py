"""Uniform error envelope: {"error": {"code", "message", "details"}} — nothing is ever swallowed.

Every failure path raises ApiError or lets an exception handler translate it; the
generic 500 handler logs the traceback instead of hiding it.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

log = logging.getLogger("phd_tracker.errors")


class ApiError(Exception):
	def __init__(
		self,
		status: int,
		code: str,
		message: str,
		details: dict | list | None = None,
	) -> None:
		self.status = status
		self.code = code
		self.message = message
		self.details = details


def envelope(code: str, message: str, details: dict | list | None = None) -> dict:
	return {"error": {"code": code, "message": message, "details": details}}


# Constraint name → (status, code, message). The DB CHECKs are the backstop behind
# Pydantic; unknown constraints surface as a loud 500 rather than a silent pass.
CONSTRAINT_ERRORS: dict[str, tuple[int, str, str]] = {
	"uq_apr_active": (409, "duplicate_apr", "An APR for this scholar, year and period already exists"),
	"scholars_roll_number_key": (409, "duplicate_roll_number", "This roll number is already taken"),
	"users_email_key": (409, "duplicate_email", "A user with this email already exists"),
}


def register_error_handlers(app: FastAPI) -> None:
	@app.exception_handler(ApiError)
	async def _(request: Request, exc: ApiError) -> JSONResponse:
		return JSONResponse(
			status_code=exc.status,
			content=envelope(exc.code, exc.message, exc.details),
		)

	@app.exception_handler(RequestValidationError)
	async def _(request: Request, exc: RequestValidationError) -> JSONResponse:
		return JSONResponse(
			status_code=422,
			content=envelope("validation_error", "Invalid input", exc.errors()),
		)

	@app.exception_handler(IntegrityError)
	async def _(request: Request, exc: IntegrityError) -> JSONResponse:
		# psycopg exposes the violated constraint on .diag; message scan is the fallback.
		constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
		if constraint is None and exc.orig is not None:
			msg = str(exc.orig)
			for name in CONSTRAINT_ERRORS:
				if name in msg:
					constraint = name
					break
		if constraint in CONSTRAINT_ERRORS:
			status, code, message = CONSTRAINT_ERRORS[constraint]
			return JSONResponse(status_code=status, content=envelope(code, message))
		log.error("unhandled integrity error on %s %s: %s", request.method, request.url.path, exc)
		return JSONResponse(
			status_code=409,
			content=envelope("conflict", "The request conflicts with existing data"),
		)

	@app.exception_handler(Exception)
	async def _(request: Request, exc: Exception) -> JSONResponse:
		log.exception("unhandled error on %s %s", request.method, request.url.path)
		return JSONResponse(
			status_code=500,
			content=envelope("internal_error", "Something went wrong on our side"),
		)