"""Pydantic schemas — the trust boundary. Literals mirror the DB CHECK constraints
exactly; anything not expressible here (cross-row rules) lives in the routers/workflow.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Designation = Literal["Professor", "Associate Professor", "Assistant Professor"]
Stage = Literal[
	"Registered",
	"Coursework",
	"Proposal Approved",
	"Research Phase",
	"Pre-Synopsis Done",
	"Thesis Submitted",
	"Viva Voce",
	"Degree Awarded",
]
Period = Literal["January-June", "July-December"]
MilestoneType = Literal[
	"Coursework Completion",
	"Proposal Approval (RDC)",
	"Pre-Synopsis Seminar",
	"Thesis Submission",
	"Viva Voce",
	"Degree Awarded",
]
MilestoneStatus = Literal["Pending", "Approved", "Rejected"]
Role = Literal["scholar", "supervisor", "admin"]


# --- shared ---

class ORMModel(BaseModel):
	model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
	items: list[T]
	total: int
	page: int
	per_page: int


# --- auth ---

class UserOut(ORMModel):
	id: uuid.UUID
	email: EmailStr
	full_name: str
	role: Role


class LoginIn(BaseModel):
	email: EmailStr
	password: str = Field(min_length=1)


class RegisterIn(BaseModel):
	email: EmailStr
	password: str = Field(min_length=8)
	full_name: str = Field(min_length=1)
	role: Role


class RefreshIn(BaseModel):
	refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
	access_token: str
	refresh_token: str
	token_type: str = "bearer"
	user: UserOut


class MeOut(UserOut):
	scholar_id: uuid.UUID | None = None
	supervisor_id: uuid.UUID | None = None


# --- supervisors ---

class SupervisorIn(BaseModel):
	full_name: str = Field(min_length=1)
	email: EmailStr
	department: str = Field(min_length=1)
	designation: Designation
	max_scholars: int = Field(default=8, ge=1, le=8)
	user_id: uuid.UUID | None = None


class SupervisorPatch(BaseModel):
	full_name: str | None = None
	email: EmailStr | None = None
	department: str | None = None
	designation: Designation | None = None
	max_scholars: int | None = Field(default=None, ge=1, le=8)
	user_id: uuid.UUID | None = None


class SupervisorOut(ORMModel):
	id: uuid.UUID
	user_id: uuid.UUID | None
	full_name: str
	email: EmailStr
	department: str
	designation: Designation
	max_scholars: int
	created_at: datetime
	updated_at: datetime


# --- scholars ---

class ScholarIn(BaseModel):
	scholar_name: str = Field(min_length=1)
	roll_number: str = Field(min_length=1)
	scholar_email: EmailStr | None = None
	department: str = Field(min_length=1)
	admission_date: date
	stage: Stage = "Registered"
	github_url: str | None = None
	supervisor_id: uuid.UUID | None = None
	user_id: uuid.UUID | None = None


class ScholarPatch(BaseModel):
	scholar_name: str | None = None
	roll_number: str | None = None
	scholar_email: EmailStr | None = None
	department: str | None = None
	admission_date: date | None = None
	stage: Stage | None = None
	github_url: str | None = None
	supervisor_id: uuid.UUID | None = None
	user_id: uuid.UUID | None = None


class ScholarOut(ORMModel):
	id: uuid.UUID
	user_id: uuid.UUID | None
	scholar_name: str
	roll_number: str
	scholar_email: EmailStr | None
	department: str
	admission_date: date
	stage: Stage
	github_url: str | None
	supervisor_id: uuid.UUID | None
	created_at: datetime
	updated_at: datetime


# --- meetings ---

class MeetingIn(BaseModel):
	scholar_id: uuid.UUID
	supervisor_id: uuid.UUID
	meeting_date: date
	agenda: str | None = None
	minutes: str | None = None
	action_items: str | None = None
	next_meeting_date: date | None = None


class MeetingPatch(BaseModel):
	meeting_date: date | None = None
	agenda: str | None = None
	minutes: str | None = None
	action_items: str | None = None
	next_meeting_date: date | None = None


class MeetingOut(ORMModel):
	id: uuid.UUID
	scholar_id: uuid.UUID
	supervisor_id: uuid.UUID
	meeting_date: date
	agenda: str | None
	minutes: str | None
	action_items: str | None
	next_meeting_date: date | None
	created_at: datetime
	updated_at: datetime


# --- progress reports (APR) ---

class ReportIn(BaseModel):
	scholar_id: uuid.UUID
	report_year: int = Field(ge=2000, le=2100)
	period: Period
	summary: str = Field(min_length=1)


class ReportPatch(BaseModel):
	summary: str | None = Field(default=None, min_length=1)
	supervisor_comment: str | None = None


class ReportOut(ORMModel):
	id: uuid.UUID
	scholar_id: uuid.UUID
	report_year: int
	period: Period
	summary: str
	supervisor_comment: str | None
	approved_on: date | None
	state: Literal["draft", "submitted", "approved", "rejected"]
	created_at: datetime
	updated_at: datetime


# --- milestones ---

class MilestoneIn(BaseModel):
	scholar_id: uuid.UUID
	milestone_type: MilestoneType
	status: MilestoneStatus = "Pending"
	approval_body: str | None = None
	resolution_number: str | None = None
	resolution_date: date | None = None
	notes: str | None = None


class MilestonePatch(BaseModel):
	status: MilestoneStatus | None = None
	approval_body: str | None = None
	resolution_number: str | None = None
	resolution_date: date | None = None
	notes: str | None = None


class MilestoneOut(ORMModel):
	id: uuid.UUID
	scholar_id: uuid.UUID
	milestone_type: MilestoneType
	status: MilestoneStatus
	approval_body: str | None
	resolution_number: str | None
	resolution_date: date | None
	notes: str | None
	created_at: datetime
	updated_at: datetime


# --- search ---

class SearchOut(BaseModel):
	scholars: list[ScholarOut]
	supervisors: list[SupervisorOut]
	meetings: list[MeetingOut]
	reports: list[ReportOut]
	milestones: list[MilestoneOut]