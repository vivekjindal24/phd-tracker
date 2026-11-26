"""Boundary models of academic administration: bulk import, coursework, admissions, the UGC
duration rules and the leadership view (PRD F16, M4, M5, Phase 4)."""

import uuid
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    CommitteeRole,
    CommitteeSeat,
    ComprehensiveResult,
    EntranceRoute,
    EthicsKind,
    InterviewResult,
    ItemState,
    Stage,
    TimeKind,
)
from app.schemas import MAX_ADJUSTMENT_DAYS, LongTitle, Name, Notes, Password, Ref, Resolution

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
        if (self.end_date - self.start_date).days > MAX_ADJUSTMENT_DAYS:
            raise ValueError(f"one adjustment cannot exceed {MAX_ADJUSTMENT_DAYS} days")
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


class TrendYear(BaseModel):
    year: str
    so_far: bool
    admitted: int
    awarded: int
    median_years_to_complete: float | None
    publications: int


class LeadershipView(BaseModel):
    unit: Ref
    total: LeadershipRow
    by_unit: list[LeadershipRow]
    at_risk: list[AtRisk]
    trends: list[TrendYear]
    as_of: date


# --- committees: a scholar's advisory committee, a department's research committee --------


class FormationIn(BaseModel):
    """One version of the committee: when it was formed, and the order that formed it."""

    formed_on: date
    reference: Resolution | None = None
    notes: Notes = ""


class CommitteeMemberIn(BaseModel):
    """Faculty of this university by id, a scholar by id (department committees), or an
    outside expert by name and institution. Which roles, and whether a seat is needed,
    depends on the committee (routers/committee.py)."""

    faculty_id: uuid.UUID | None = None
    scholar_member_id: uuid.UUID | None = None
    name: Name | None = None
    institution: Name | None = None
    email: EmailStr | None = None  # required for an outside member: how to reach them
    role: CommitteeRole = "member"
    seat: CommitteeSeat | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> "CommitteeMemberIn":
        if (self.email is None) == (self.name is not None):
            raise ValueError("an outside member needs an email; others take none")
        outside = (self.name, self.institution)
        kinds = (
            self.faculty_id is not None,
            self.scholar_member_id is not None,
            all(v is not None for v in outside),
        )
        if sum(kinds) != 1 or (not kinds[2] and any(v is not None for v in outside)):
            raise ValueError(
                "give a faculty member, a scholar, or an outside expert's name and institution"
            )
        return self


class CommitteeMemberPatch(BaseModel):
    """A role or seat change (current version only), or a corrected outside expert's name,
    institution or email (any version)."""

    role: CommitteeRole | None = None
    seat: CommitteeSeat | None = None
    name: Name | None = None
    institution: Name | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def _something(self) -> "CommitteeMemberPatch":
        given = (self.role, self.seat, self.name, self.institution, self.email)
        if all(v is None for v in given):
            raise ValueError("give a role, a seat, a name, an institution or an email")
        return self


class CommitteeMemberOut(BaseModel):
    id: uuid.UUID
    name: str
    institution: str
    email: str | None  # an outside member's; shown only to those who keep the committee
    external: bool
    role: CommitteeRole
    seat: CommitteeSeat | None


class FormationOut(BaseModel):
    id: uuid.UUID
    formed_on: date
    reference: str | None
    notes: str
    secretary: str | None  # an advisory committee's supervisor when it was formed
    members: list[CommitteeMemberOut]


class CommitteeView(BaseModel):
    title: str  # "Research Advisory Committee", or the university's name for a department's
    convener: str | None  # an advisory committee's supervisor today
    formations: list[FormationOut]  # newest (the current committee) first
    can_manage: bool


# --- research ethics ---------------------------------------------------------------------


class EthicsIn(BaseModel):
    """A committee's clearance, or `not_required` with the reason in `notes`."""

    kind: EthicsKind
    committee: Name | None = None
    approval_number: Resolution | None = None
    approved_on: date | None = None
    valid_until: date | None = None
    notes: Notes = ""

    @model_validator(mode="after")
    def _fields_match_kind(self) -> "EthicsIn":
        approval = (self.committee, self.approval_number, self.approved_on, self.valid_until)
        if self.kind == "not_required":
            if any(v is not None for v in approval) or not self.notes:
                raise ValueError("'not required' takes only the reason, in notes")
            return self
        if not self.approval_number or self.approved_on is None:
            raise ValueError("a clearance needs its approval number and approval date")
        if self.valid_until is not None and self.valid_until < self.approved_on:
            raise ValueError("the clearance ends before it was approved")
        return self


class EthicsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: EthicsKind
    committee: str | None
    approval_number: str | None
    approved_on: date | None
    valid_until: date | None
    notes: str


class EthicsView(BaseModel):
    records: list[EthicsOut]
    required: bool  # university setting require_ethics: the thesis waits for a record
    satisfied: bool
    can_manage: bool


# --- comprehensive examination (Form VI) -------------------------------------------------


class ComprehensiveIn(BaseModel):
    """The next attempt: the month it was held (its first day) and the result."""

    held_in: date
    result: ComprehensiveResult
    notes: Notes = ""

    @model_validator(mode="after")
    def _a_month(self) -> "ComprehensiveIn":
        if self.held_in.day != 1:
            raise ValueError("give the month as its first day")
        return self


class ComprehensiveAttempt(BaseModel):
    id: uuid.UUID
    attempt: int
    held_in: date
    result: ComprehensiveResult
    notes: str


class ComprehensiveView(BaseModel):
    attempts: list[ComprehensiveAttempt]  # in order, first attempt first
    passed: bool
    can_manage: bool
