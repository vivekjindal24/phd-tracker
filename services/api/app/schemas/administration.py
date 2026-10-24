"""Boundary models of academic administration: bulk import, coursework, admissions, the UGC
duration rules and the leadership view (PRD F16, M4, M5, Phase 4)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    EntranceRoute,
    InterviewResult,
    ItemState,
    Stage,
    TimeKind,
)
from app.schemas import LongTitle, Name, Notes, Password, Ref, Resolution

# --- bulk import ------------------------------------------------------------------------


class ImportRowError(BaseModel):
    row: int
    column: str
    message: str


class ImportSkipped(BaseModel):
    row: int
    what: str


class ImportReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: Literal["faculty", "scholars", "history"]
    dry_run: bool
    total_rows: int
    to_create: int
    created: int
    already_present: list[ImportSkipped]
    errors: list[ImportRowError]
    invitations_sent: int | None
    invitations_failed: list[str]


# --- coursework -------------------------------------------------------------------------

CourseCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
Semester = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Grade = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5)]


class CourseIn(BaseModel):
    unit_id: uuid.UUID
    code: CourseCode
    title: LongTitle
    credits: float = Field(gt=0, le=20)


class CourseUpdate(BaseModel):
    code: CourseCode | None = None
    title: LongTitle | None = None
    credits: float | None = Field(default=None, gt=0, le=20)


class CourseOut(BaseModel):
    id: uuid.UUID
    unit: Ref
    code: str
    title: str
    credits: float


class EnrolmentIn(BaseModel):
    scholar_id: uuid.UUID
    course_id: uuid.UUID
    semester: Semester
    grade: Grade | None = None
    grade_points: float | None = Field(default=None, ge=0, le=10)


class EnrolmentUpdate(BaseModel):
    semester: Semester | None = None
    grade: Grade | None = None
    grade_points: float | None = Field(default=None, ge=0, le=10)


class EnrolmentOut(BaseModel):
    id: uuid.UUID
    course: CourseOut
    semester: str
    grade: str | None
    grade_points: float | None


class ClearanceRef(BaseModel):
    id: uuid.UUID
    state: ItemState
    waiting_on: str | None
    cleared_on: date | None


class CourseworkView(BaseModel):
    scholar: Ref
    enrolments: list[EnrolmentOut]
    credits: float
    cgpa: float | None
    min_credits: float
    min_cgpa: float
    problems: list[str]
    clearance: ClearanceRef | None
    can_manage: bool
    locked: bool


class ClearanceIn(BaseModel):
    scholar_id: uuid.UUID


# --- admissions -------------------------------------------------------------------------

Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]


class AdmissionIn(BaseModel):
    candidate_name: Name
    email: EmailStr
    phone: Phone | None = None
    unit_id: uuid.UUID
    entrance_route: EntranceRoute
    entrance_score: float | None = Field(default=None, ge=0, le=9999)
    interview_date: date | None = None
    interview_result: InterviewResult = "pending"
    admitted_on: date | None = None


class AdmissionUpdate(BaseModel):
    candidate_name: Name | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    entrance_route: EntranceRoute | None = None
    entrance_score: float | None = Field(default=None, ge=0, le=9999)
    interview_date: date | None = None
    interview_result: InterviewResult | None = None
    admitted_on: date | None = None


class AdmissionOut(BaseModel):
    id: uuid.UUID
    candidate_name: str
    email: str
    phone: str | None
    unit: Ref
    entrance_route: EntranceRoute
    entrance_score: float | None
    interview_date: date | None
    interview_result: InterviewResult
    admitted_on: date | None
    scholar_id: uuid.UUID | None
    can_edit: bool


class ConvertIn(BaseModel):
    roll_number: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]
    research_title: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    password: Password | None = None  # omitted: a set-password email goes out


class ConvertOut(BaseModel):
    scholar_id: uuid.UUID
    invitation_sent: bool


# --- duration rules & leadership --------------------------------------------------------


class TimeAdjustmentIn(BaseModel):
    kind: TimeKind
    start_date: date
    end_date: date
    resolution_number: Resolution | None = None
    notes: Notes = ""

    @model_validator(mode="after")
    def _ordered(self) -> "TimeAdjustmentIn":
        if self.end_date < self.start_date:
            raise ValueError("the end date is before the start date")
        return self


class TimeAdjustmentOut(BaseModel):
    id: uuid.UUID
    kind: TimeKind
    start_date: date
    end_date: date
    days: int
    resolution_number: str | None
    notes: str


class DurationView(BaseModel):
    scholar: Ref
    admission_date: date | None
    limit_date: date | None
    days_left: int | None
    status: Literal["ok", "near", "over", "done", "left", "unknown"]
    extension_days: int
    relaxation_days: int
    leave_days: int
    warnings: list[str]
    adjustments: list[TimeAdjustmentOut]
    max_years: int
    can_manage: bool


class LeadershipRow(BaseModel):
    unit: Ref
    current: int
    completed: int
    median_years_to_complete: float | None
    left: int
    withdrawn: int
    cancelled: int
    dropout_rate: float | None
    supervisors: int
    supervisors_at_cap: int
    average_load: float | None


class AtRisk(BaseModel):
    scholar: Ref
    stage: Stage
    limit_date: date | None
    reasons: list[str]


class LeadershipView(BaseModel):
    unit: Ref
    total: LeadershipRow
    by_unit: list[LeadershipRow]
    at_risk: list[AtRisk]
    as_of: date
