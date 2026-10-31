"""Pydantic boundary models. Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    WHATSAPP_NUMBER_RE,
    ApprovalBody,
    AssignedRole,
    CommentTarget,
    CoSupervision,
    Designation,
    FileOwner,
    ItemState,
    ItemType,
    LeftReason,
    MeetingShare,
    MilestoneStatus,
    MilestoneType,
    ModuleKey,
    NotificationCategory,
    PanelKind,
    Period,
    SeminarGraders,
    SeminarStatus,
    Stage,
    StepKind,
    TodoPart,
    TodoStatus,
)

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Password = Annotated[str, StringConstraints(min_length=10, max_length=200)]
UnitCode = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{1,32}$")
]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- auth -------------------------------------------------------------------------------


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth token type, not a secret


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: Password


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class SetPasswordIn(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    password: Password


class SsoExchangeIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)


class UnitRoleOut(BaseModel):
    role: AssignedRole
    unit_id: uuid.UUID
    unit_name: str
    unit_path: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    unit_roles: list[UnitRoleOut]
    office_roles: list[AssignedRole]
    faculty_id: uuid.UUID | None
    scholar_id: uuid.UUID | None
    is_root_admin: bool
    co_supervision: CoSupervision
    modules: dict[str, bool]
    unread_notifications: int
    email_muted: list[str]
    whatsapp_available: bool  # the server has WhatsApp configured
    whatsapp_number: str | None
    whatsapp_muted: list[str]


# --- org --------------------------------------------------------------------------------


class OrgUnitOut(Out):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    kind: str
    code: str
    path: str


class OrgUnitCreate(BaseModel):
    parent_id: uuid.UUID
    name: Name
    kind: Name
    code: UnitCode


class OrgUnitUpdate(BaseModel):
    name: Name | None = None
    kind: Name | None = None
    parent_id: uuid.UUID | None = None


# --- people -----------------------------------------------------------------------------


class FacultyProfileIn(BaseModel):
    unit_id: uuid.UUID
    designation: Designation
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = (
        None
    )
    can_supervise: bool = True


class ScholarProfileIn(BaseModel):
    unit_id: uuid.UUID
    roll_number: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)
    ]
    research_title: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    admission_date: date | None = None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Name
    password: Password | None = None  # omitted: the person gets a set-password email
    faculty: FacultyProfileIn | None = None
    scholar: ScholarProfileIn | None = None

    @model_validator(mode="after")
    def _one_profile(self) -> "UserCreate":
        if self.faculty and self.scholar:
            raise ValueError("a user is either faculty or a scholar, not both")
        return self


class UserUpdate(BaseModel):
    full_name: Name | None = None
    is_active: bool | None = None


class UserOut(Out):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    has_password: bool
    created_at: datetime


class RoleAssignmentIn(BaseModel):
    user_id: uuid.UUID
    role: AssignedRole
    unit_id: uuid.UUID | None = None


class RoleAssignmentOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    role: AssignedRole
    unit_id: uuid.UUID | None


# --- settings ---------------------------------------------------------------------------


class ChainStep(BaseModel):
    kind: StepKind


class ChainIn(BaseModel):
    steps: list[ChainStep] = Field(min_length=1, max_length=8)


class RubricCriterion(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    max: int = Field(ge=1, le=100)


Rubric = Annotated[list[RubricCriterion], Field(min_length=1, max_length=10)]


class SettingsOut(BaseModel):
    co_supervision: CoSupervision
    require_hardcopy: bool
    require_no_dues: bool
    seminar_graders: SeminarGraders
    seminar_rubric: list[RubricCriterion]
    min_coursework_credits: float
    min_coursework_cgpa: float
    max_duration_years: int
    max_extension_days: int
    max_relaxation_days: int
    max_maternity_leave_days: int
    modules: dict[ModuleKey, bool]
    chains: dict[ItemType, list[ChainStep]]
    email_configured: bool  # from the server's environment; forms offer email links only if set


class SettingsUpdate(BaseModel):
    co_supervision: CoSupervision | None = None
    require_hardcopy: bool | None = None
    require_no_dues: bool | None = None
    seminar_graders: SeminarGraders | None = None
    seminar_rubric: Rubric | None = None
    min_coursework_credits: float | None = Field(default=None, ge=0, le=40)
    min_coursework_cgpa: float | None = Field(default=None, ge=0, le=10)
    max_duration_years: int | None = Field(default=None, ge=3, le=12)
    max_extension_days: int | None = Field(default=None, ge=0, le=1825)
    max_relaxation_days: int | None = Field(default=None, ge=0, le=1825)
    max_maternity_leave_days: int | None = Field(default=None, ge=0, le=1825)

    @model_validator(mode="after")
    def _unique_criteria(self) -> "SettingsUpdate":
        if self.seminar_rubric:
            names = [c.name.lower() for c in self.seminar_rubric]
            if len(names) != len(set(names)):
                raise ValueError("rubric criteria must have different names")
        return self


class ModuleUpdate(BaseModel):
    enabled: bool


# --- notifications ----------------------------------------------------------------------


class NotificationOut(Out):
    id: uuid.UUID
    category: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class EmailMutedIn(BaseModel):
    email_muted: list[NotificationCategory] = Field(max_length=20)


class WhatsappIn(BaseModel):
    """Own number only; null clears it (opts out)."""

    whatsapp_number: Annotated[str, StringConstraints(pattern=WHATSAPP_NUMBER_RE)] | None
    whatsapp_muted: list[NotificationCategory] = Field(max_length=20)


# --- files ------------------------------------------------------------------------------


class UploadIn(BaseModel):
    table_name: FileOwner
    record_id: uuid.UUID
    file_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    content_type: Annotated[str, StringConstraints(max_length=200)]
    size_bytes: int = Field(gt=0)


class UploadOut(BaseModel):
    file_id: uuid.UUID
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str]
    expires_in: int


class FileOut(Out):
    id: uuid.UUID
    file_name: str
    content_type: str
    size_bytes: int
    status: str
    uploaded_by: uuid.UUID
    created_at: datetime


class DownloadOut(BaseModel):
    url: str
    expires_in: int


# --- directory --------------------------------------------------------------------------


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class ScholarOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    roll_number: str
    unit: Ref
    stage: Stage
    research_title: str | None
    admission_date: date | None
    supervisor: Ref | None
    co_supervisor: Ref | None
    left_on: date | None
    left_reason: LeftReason | None


class ScholarUpdate(BaseModel):
    research_title: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None
    ) = None
    admission_date: date | None = None
    stage: Stage | None = None
    unit_id: uuid.UUID | None = None
    roll_number: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
    ) = None
    # Withdrawn / cancelled: both together, or both null to undo (PRD Phase 4).
    left_on: date | None = None
    left_reason: LeftReason | None = None

    @model_validator(mode="after")
    def _left_together(self) -> "ScholarUpdate":
        fields = self.model_fields_set & {"left_on", "left_reason"}
        if fields and (len(fields) == 1 or (self.left_on is None) != (self.left_reason is None)):
            raise ValueError("give both the date and the reason the scholar left, or neither")
        return self


class AssignIn(BaseModel):
    faculty_id: uuid.UUID | None


class FacultyOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    email: str
    unit: Ref
    designation: Designation
    employee_id: str | None
    can_supervise: bool
    max_scholars: int
    load: int


class FacultyUpdate(BaseModel):
    designation: Designation | None = None
    max_scholars: int | None = Field(default=None, ge=0, le=20)
    can_supervise: bool | None = None
    employee_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)] | None = (
        None
    )
    unit_id: uuid.UUID | None = None


# --- meetings ---------------------------------------------------------------------------

Agenda = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]


class MeetingIn(BaseModel):
    scholar_id: uuid.UUID
    supervisor_id: uuid.UUID | None = None
    meeting_date: date
    agenda: Agenda
    minutes: LongText = ""
    action_items: LongText = ""
    next_meeting_date: date | None = None
    shared_with: list[MeetingShare] = Field(default_factory=list, max_length=3)


class MeetingUpdate(BaseModel):
    meeting_date: date | None = None
    agenda: Agenda | None = None
    minutes: LongText | None = None
    action_items: LongText | None = None
    next_meeting_date: date | None = None
    shared_with: list[MeetingShare] | None = Field(default=None, max_length=3)


class MeetingOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    supervisor: Ref
    meeting_date: date
    redacted: bool
    agenda: str | None
    minutes: str | None
    action_items: str | None
    next_meeting_date: date | None
    shared_with: list[MeetingShare]
    can_edit: bool
    can_share: bool
    created_at: datetime
    updated_at: datetime


# --- approvable items -------------------------------------------------------------------

Comment = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class ChainStepView(BaseModel):
    kind: StepKind
    label: str
    status: Literal["done", "current", "upcoming"]


class SendBackTarget(BaseModel):
    to_step: int | None
    label: str


class HistoryEntry(BaseModel):
    action: str
    actor: str
    step: str | None
    to: str | None
    comment: str | None
    at: datetime


class ItemView(BaseModel):
    item_type: ItemType
    id: uuid.UUID
    label: str
    title: str
    scholar: Ref
    state: ItemState
    current_step: int | None
    waiting_on: str | None
    chain: list[ChainStepView]
    submitted_at: datetime | None
    approved_at: datetime | None
    content: dict[str, Any]
    can_edit: bool
    can_submit: bool
    can_resubmit: bool
    can_act: bool
    send_back_targets: list[SendBackTarget]
    blocked_reason: str | None
    history: list[HistoryEntry]


class NoDuesMine(BaseModel):
    required: bool  # university setting require_no_dues: the thesis waits for it
    item: ItemView | None


class ApproveIn(BaseModel):
    comment: Comment | None = None


class SendBackIn(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    to_step: int | None = Field(default=None, ge=0)


class QueueEntry(BaseModel):
    item_type: ItemType
    id: uuid.UUID
    label: str
    title: str
    scholar: Ref
    step: str
    waiting_since: datetime
    days_waiting: int


# --- progress reports -------------------------------------------------------------------

Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=20000)]


class ReportIn(BaseModel):
    report_year: int = Field(ge=2000, le=2100)
    period: Period
    summary: Summary


class ReportUpdate(BaseModel):
    summary: Summary


class ReportRow(BaseModel):
    id: uuid.UUID
    scholar: Ref
    report_year: int
    period: Period
    state: ItemState
    waiting_on: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    updated_at: datetime


# --- RDC register -----------------------------------------------------------------------

Resolution = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class MilestoneIn(BaseModel):
    scholar_id: uuid.UUID
    milestone_type: MilestoneType
    status: MilestoneStatus = "Pending"
    approval_body: ApprovalBody
    resolution_number: Resolution | None = None
    resolution_date: date | None = None
    notes: Notes = ""


class MilestoneUpdate(BaseModel):
    milestone_type: MilestoneType | None = None
    status: MilestoneStatus | None = None
    approval_body: ApprovalBody | None = None
    resolution_number: Resolution | None = None
    resolution_date: date | None = None
    notes: Notes | None = None


class MilestoneOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    roll_number: str
    unit: Ref
    milestone_type: MilestoneType
    status: MilestoneStatus
    approval_body: ApprovalBody
    resolution_number: str | None
    resolution_date: date | None
    notes: str
    updated_at: datetime


# --- progress seminars ------------------------------------------------------------------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Venue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class SeminarIn(BaseModel):
    unit_id: uuid.UUID
    title: Title
    starts_at: datetime
    venue: Venue = ""
    report_due: date
    report_year: int = Field(ge=2000, le=2100)
    period: Period
    notes: Notes = ""
    scholar_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    panel_faculty_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)


class SeminarUpdate(BaseModel):
    title: Title | None = None
    starts_at: datetime | None = None
    venue: Venue | None = None
    report_due: date | None = None
    report_year: int | None = Field(default=None, ge=2000, le=2100)
    period: Period | None = None
    notes: Notes | None = None
    scholar_ids: list[uuid.UUID] | None = Field(default=None, min_length=1, max_length=200)
    panel_faculty_ids: list[uuid.UUID] | None = Field(default=None, max_length=30)


class SeminarRow(BaseModel):
    id: uuid.UUID
    unit: Ref
    title: str
    starts_at: datetime
    venue: str
    report_due: date
    report_year: int
    period: Period
    status: SeminarStatus
    scholar_count: int


class SeminarScholarView(BaseModel):
    scholar: Ref
    roll_number: str
    supervisor: str | None
    report_state: ItemState | None
    hardcopy_received_on: date | None
    finalised_at: datetime | None


class PanelMember(BaseModel):
    faculty_id: uuid.UUID
    name: str
    kind: PanelKind


class SeminarDetail(SeminarRow):
    notes: str
    scholars: list[SeminarScholarView]
    panel: list[PanelMember]
    can_manage: bool
    require_hardcopy: bool
    is_grader: bool
    can_attend: bool


class HardcopyIn(BaseModel):
    received_on: date | None


# --- seminar grading & to-dos -----------------------------------------------------------


class GradeIn(BaseModel):
    scores: dict[str, float] = Field(min_length=1, max_length=10)
    comment: Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)] = ""


class Point(BaseModel):
    part: TodoPart
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class DraftIn(BaseModel):
    points: list[Point] = Field(max_length=40)


class FinaliseIn(BaseModel):
    points: list[Point] = Field(max_length=40)


class GradeView(BaseModel):
    grader: str
    scores: dict[str, float]
    rubric: list[RubricCriterion]
    total: float
    max_total: int
    comment: str
    submitted_at: datetime


class TodoOut(Out):
    id: uuid.UUID
    scholar_id: uuid.UUID
    part: TodoPart
    text: str
    status: TodoStatus
    done_at: datetime | None
    created_at: datetime


class TodoUpdate(BaseModel):
    status: TodoStatus


class ReviewView(BaseModel):
    seminar_id: uuid.UUID
    seminar_title: str
    scholar: Ref
    rubric: list[RubricCriterion]
    grades: list[GradeView]
    average_percent: float | None
    draft_points: list[Point]
    finalised_at: datetime | None
    todos: list[TodoOut]
    can_grade: bool
    my_grade: GradeView | None
    can_finalise: bool
    ai_available: bool
    parts: dict[str, str]


# --- comments ---------------------------------------------------------------------------


class CommentIn(BaseModel):
    table_name: CommentTarget
    record_id: uuid.UUID
    body: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class CommentOut(BaseModel):
    id: uuid.UUID
    author: str
    author_id: uuid.UUID
    body: str
    created_at: datetime
    mine: bool


# --- shared by the module schemas (schemas/research.py, schemas/administration.py) ---

LongTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
