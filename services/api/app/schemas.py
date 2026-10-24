"""Pydantic boundary models. Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    ApprovalBody,
    AssignedRole,
    CommentTarget,
    ConferenceType,
    CoSupervision,
    Designation,
    DocKind,
    EntranceRoute,
    FileOwner,
    Indexing,
    InterviewResult,
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
    PubStatus,
    PubType,
    Recommendation,
    SeminarGraders,
    SeminarStatus,
    Stage,
    StepKind,
    TimeKind,
    TodoPart,
    TodoStatus,
    VivaOutcome,
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


class SettingsUpdate(BaseModel):
    co_supervision: CoSupervision | None = None
    require_hardcopy: bool | None = None
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


# --- publications & conferences ---------------------------------------------------------

LongTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Doi = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^10\.\d{4,9}/\S{1,200}$")]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=50)]


class PublicationIn(BaseModel):
    title: LongTitle
    authors: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    pub_type: PubType
    venue: LongTitle
    issn_isbn: ShortText | None = None
    indexing: list[Indexing] = Field(default_factory=list, max_length=4)
    doi: Doi | None = None
    pub_year: int = Field(ge=1950, le=2100)
    pub_status: PubStatus


class PublicationUpdate(BaseModel):
    title: LongTitle | None = None
    authors: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
        | None
    ) = None
    pub_type: PubType | None = None
    venue: LongTitle | None = None
    issn_isbn: ShortText | None = None
    indexing: list[Indexing] | None = Field(default=None, max_length=4)
    doi: Doi | None = None
    pub_year: int | None = Field(default=None, ge=1950, le=2100)
    pub_status: PubStatus | None = None


class VerificationIn(BaseModel):
    """What the Library confirms at its step (PRD M1)."""

    indexing: list[Indexing] = Field(max_length=4)
    doi: Doi | None = None


class PublicationRow(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    venue: str
    pub_type: PubType
    pub_year: int
    indexing: list[Indexing]
    state: ItemState
    waiting_on: str | None
    updated_at: datetime


class ConferenceIn(BaseModel):
    event_name: LongTitle
    event_type: ConferenceType
    event_date: date
    place: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    title: LongTitle | None = None


class ConferenceUpdate(BaseModel):
    event_name: LongTitle | None = None
    event_type: ConferenceType | None = None
    event_date: date | None = None
    place: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None
    title: LongTitle | None = None


class ConferenceOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    event_name: str
    event_type: ConferenceType
    event_date: date
    place: str
    title: str | None
    can_edit: bool


# --- documents & thesis -----------------------------------------------------------------


class DocumentIn(BaseModel):
    title: LongTitle
    doc_kind: DocKind


class DocumentUpdate(BaseModel):
    title: LongTitle | None = None
    doc_kind: DocKind | None = None


class VersionIn(BaseModel):
    file_id: uuid.UUID
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""


class VersionOut(BaseModel):
    id: uuid.UUID
    version_no: int
    note: str
    file_id: uuid.UUID
    file_name: str
    size_bytes: int
    created_at: datetime


class DocumentOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    doc_kind: DocKind
    updated_at: datetime
    can_edit: bool
    versions: list[VersionOut]


class ThesisIn(BaseModel):
    title: LongTitle


class PlagiarismIn(BaseModel):
    plagiarism_tool: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    plagiarism_score: float = Field(ge=0, le=100)


class ExaminersIn(BaseModel):
    examiners: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]


class ThesisRow(BaseModel):
    id: uuid.UUID
    scholar: Ref
    title: str
    state: ItemState
    waiting_on: str | None
    updated_at: datetime


class ExaminerReportIn(BaseModel):
    examiner_name: Name
    institution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    received_on: date
    recommendation: Recommendation
    notes: Notes = ""


class ExaminerReportUpdate(BaseModel):
    examiner_name: Name | None = None
    institution: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )
    received_on: date | None = None
    recommendation: Recommendation | None = None
    notes: Notes | None = None


class VivaIn(BaseModel):
    held_on: date
    venue: Venue = ""
    panel: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    outcome: VivaOutcome
    notes: Notes = ""


class VivaUpdate(BaseModel):
    held_on: date | None = None
    venue: Venue | None = None
    panel: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    outcome: VivaOutcome | None = None
    notes: Notes | None = None


class DepositIn(BaseModel):
    deposited_on: date
    handle_url: Annotated[
        str, StringConstraints(strip_whitespace=True, pattern=r"^https?://\S{3,500}$")
    ]


class ExaminerReportView(BaseModel):
    id: uuid.UUID
    examiner_name: str | None
    institution: str | None
    received_on: date
    recommendation: Recommendation
    notes: str
    released: bool


class VivaView(BaseModel):
    id: uuid.UUID
    held_on: date
    venue: str
    panel: str
    outcome: VivaOutcome
    notes: str


class DepositView(BaseModel):
    id: uuid.UUID
    deposited_on: date
    handle_url: str


class EvaluationView(BaseModel):
    thesis_id: uuid.UUID
    names_hidden: bool
    reports: list[ExaminerReportView]
    unreleased_count: int
    vivas: list[VivaView]
    deposit: DepositView | None
    can_record_reports: bool
    can_record_viva: bool
    can_record_deposit: bool


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
