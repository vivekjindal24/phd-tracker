"""Pydantic boundary models. Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    NOTICE_SIGNERS,
    PHD_FORMS,
    WHATSAPP_NUMBER_RE,
    AppealsTo,
    ApprovalBody,
    AssignedRole,
    Assistantship,
    AuditAction,
    Category,
    CommentTarget,
    CoSupervision,
    DateFormat,
    Designation,
    FileOwner,
    FileSlot,
    FormAnswer,
    Gender,
    GrievanceCategory,
    GrievanceStatus,
    ItemState,
    ItemType,
    LeftReason,
    MeetingShare,
    MilestoneStatus,
    MilestoneType,
    ModuleKey,
    MutableCategory,
    NoticeSigner,
    PanelKind,
    Period,
    Rating,
    SeminarGraders,
    SeminarKind,
    SeminarMarking,
    SeminarRecommendation,
    SeminarStatus,
    SigningAction,
    Stage,
    StepKind,
    StudyMode,
    SupervisionRole,
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
    # an authenticator code or a recovery code, while two-factor login is required
    code: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=6, max_length=20)] | None
    ) = None


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=200)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth token type, not a secret
    recovery_codes: list[str] | None = None  # shown once, at two-factor setup


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
    is_reviewer: bool
    roles: list[str]
    unit_roles: list[UnitRoleOut]
    office_roles: list[AssignedRole]
    faculty_id: uuid.UUID | None
    scholar_id: uuid.UUID | None
    is_root_admin: bool
    co_supervision: CoSupervision
    date_format: DateFormat  # how the university writes dates on every screen
    modules: dict[str, bool]
    unread_notifications: int
    email_muted: list[str]
    whatsapp_available: bool  # the server has WhatsApp configured
    whatsapp_number: str | None
    whatsapp_muted: list[str]


MAX_ADJUSTMENT_DAYS = 1825  # five years: the most any time limit or single adjustment may be

# --- org --------------------------------------------------------------------------------


class OrgUnitOut(Out):
    id: uuid.UUID
    parent_id: uuid.UUID | None
    name: str
    kind: str
    code: str
    path: str
    cross_unit_directory: bool


class OrgUnitCreate(BaseModel):
    parent_id: uuid.UUID
    name: Name
    kind: Name
    code: UnitCode


class OrgUnitUpdate(BaseModel):
    name: Name | None = None
    kind: Name | None = None
    parent_id: uuid.UUID | None = None
    cross_unit_directory: bool = False  # exclude_unset: absent leaves it, null is a 422


class FacultyRequestIn(BaseModel):
    """Exactly one of seminar_id / scholar_id, matching `kind` (thesis examiners never come
    here: the Exam Office records them)."""

    kind: Literal["seminar_panel", "co_supervisor"]
    seminar_id: uuid.UUID | None = None
    scholar_id: uuid.UUID | None = None
    email: EmailStr
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""

    @model_validator(mode="after")
    def _target_matches_kind(self) -> "FacultyRequestIn":
        wanted = self.seminar_id if self.kind == "seminar_panel" else self.scholar_id
        other = self.scholar_id if self.kind == "seminar_panel" else self.seminar_id
        if wanted is None or other is not None:
            raise ValueError("give the seminar or the scholar this request is for")
        return self


class FacultyRequestOut(BaseModel):
    id: uuid.UUID
    kind: str
    target: str
    email: str
    status: Literal["pending", "accepted", "declined", "cancelled", "expired"]
    note: str
    requested_by_name: str
    faculty_name: str | None
    created_at: datetime
    expires_at: datetime


class FacultyRequestList(BaseModel):
    incoming: list[FacultyRequestOut]
    sent: list[FacultyRequestOut]


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
    email: EmailStr | None = None
    full_name: Name | None = None
    is_active: bool | None = None


class UserOut(Out):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    has_password: bool
    created_at: datetime


class SignatureOut(BaseModel):
    image: str  # a data: URL, small enough to send inline
    uploaded_at: datetime
    uploaded_by_self: bool
    confirmed_at: datetime | None


class PendingSignatureOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    signature: SignatureOut


class RoleAssignmentIn(BaseModel):
    user_id: uuid.UUID
    role: AssignedRole
    unit_id: uuid.UUID | None = None


class RoleAssignmentOut(Out):
    id: uuid.UUID
    user_id: uuid.UUID
    role: AssignedRole
    unit_id: uuid.UUID | None


class RoleHolderOut(BaseModel):
    id: uuid.UUID  # the role assignment
    role: AssignedRole
    unit_id: uuid.UUID | None  # None for a university-wide office
    user_id: uuid.UUID
    full_name: str
    email: str


# --- settings ---------------------------------------------------------------------------


class ChainStep(BaseModel):
    kind: StepKind


class ChainIn(BaseModel):
    steps: list[ChainStep] = Field(min_length=1, max_length=8)


class RubricCriterion(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    max: int = Field(ge=1, le=100)


Rubric = Annotated[list[RubricCriterion], Field(min_length=1, max_length=10)]
FormQuestion = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class SeminarForm(BaseModel):
    """How one kind of seminar is marked (PRD F15): rubric scores, or the university's own form
    questions answered yes/no with a recommendation. `form_name` is what its report is called
    there ("Form VII")."""

    marking: SeminarMarking
    form_name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    questions: list[FormQuestion] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def _questions_when_asked(self) -> "SeminarForm":
        if self.marking == "questions" and not self.questions:
            raise ValueError("a form needs at least one question")
        if len({q.lower() for q in self.questions}) != len(self.questions):
            raise ValueError("form questions must be different")
        return self


class PhdFormName(BaseModel):
    """How the university names one form of the PhD file; empty: Anveshan's."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] = ""
    number: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] = ""
    copy_to: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    ] = Field(default_factory=list, max_length=20)


class PhdIndexRow(BaseModel):
    """One row of the university's own index: its description, and the records that fill it
    (phd_index.SOURCES); none: a paper Anveshan does not hold."""

    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    sources: list[str] = Field(default_factory=list, max_length=10)


def _known_forms(forms: dict[str, "PhdFormName"] | None) -> dict[str, "PhdFormName"] | None:
    unknown = sorted(set(forms or {}) - set(PHD_FORMS))
    if unknown:
        raise ValueError(f"no such form: {', '.join(unknown)}")
    return forms


class AprSection(BaseModel):
    """One section of the progress report template: its heading and a hint for the scholar."""

    name: Name
    hint: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] = ""


AprTemplate = Annotated[list[AprSection], Field(min_length=1, max_length=10)]


class SettingsOut(BaseModel):
    university_address: str
    department_committee_name: str
    co_supervision: CoSupervision
    require_hardcopy: bool
    require_no_dues: bool
    require_ethics: bool
    require_two_factor: bool
    require_signing: bool
    apr_custom_template: bool
    apr_sections: list[AprSection]  # the university's own list, kept while the toggle is off
    apr_template: list[AprSection]  # what scholars fill today
    seminar_graders: SeminarGraders
    seminar_rubric: list[RubricCriterion]
    seminar_forms: dict[SeminarKind, SeminarForm]
    phd_forms: dict[str, PhdFormName]  # every form of the PhD file, as this university names it
    phd_form_defaults: dict[str, str]  # Anveshan's title of each, in career order
    phd_index: list[PhdIndexRow]  # the university's own index; empty: Anveshan's annexures
    phd_sources: list[dict[str, str]]  # what a row may draw on: key, label, group
    exam_controller_id: uuid.UUID | None  # who signs notices as Controller of Examinations
    date_format: DateFormat
    min_coursework_credits: float
    min_coursework_cgpa: float
    max_duration_years: int
    max_extension_days: int
    max_relaxation_days: int
    max_maternity_leave_days: int
    min_duration_years: int
    max_plagiarism_percent: float
    min_publications: int
    publications_indexed_only: bool
    publication_file_required: bool
    grievance_appeals_to: AppealsTo
    modules: dict[ModuleKey, bool]
    chains: dict[ItemType, list[ChainStep]]
    email_configured: bool  # from the server's environment; forms offer email links only if set


class SettingsUpdate(BaseModel):
    university_address: str | None = Field(default=None, max_length=500)
    department_committee_name: Name | None = None
    co_supervision: CoSupervision | None = None
    require_hardcopy: bool | None = None
    require_no_dues: bool | None = None
    require_ethics: bool | None = None
    require_two_factor: bool | None = None
    require_signing: bool | None = None
    apr_custom_template: bool | None = None
    apr_sections: AprTemplate | None = None
    seminar_graders: SeminarGraders | None = None
    seminar_rubric: Rubric | None = None
    seminar_forms: dict[SeminarKind, SeminarForm] | None = None  # merged per kind
    phd_forms: dict[str, PhdFormName] | None = None  # merged per form
    phd_index: list[PhdIndexRow] | None = Field(default=None, max_length=80)  # replaced whole
    date_format: DateFormat | None = None
    min_coursework_credits: float | None = Field(default=None, ge=0, le=40)
    min_coursework_cgpa: float | None = Field(default=None, ge=0, le=10)
    max_duration_years: int | None = Field(default=None, ge=3, le=12)
    max_extension_days: int | None = Field(default=None, ge=0, le=MAX_ADJUSTMENT_DAYS)
    max_relaxation_days: int | None = Field(default=None, ge=0, le=MAX_ADJUSTMENT_DAYS)
    max_maternity_leave_days: int | None = Field(default=None, ge=0, le=MAX_ADJUSTMENT_DAYS)
    min_duration_years: int | None = Field(default=None, ge=0, le=6)
    max_plagiarism_percent: float | None = Field(default=None, ge=0, le=100)
    min_publications: int | None = Field(default=None, ge=0, le=10)
    publications_indexed_only: bool | None = None
    publication_file_required: bool | None = None
    grievance_appeals_to: AppealsTo | None = None

    @model_validator(mode="after")
    def _unique_criteria(self) -> "SettingsUpdate":
        _known_forms(self.phd_forms)
        if self.seminar_rubric:
            names = [c.name.lower() for c in self.seminar_rubric]
            if len(names) != len(set(names)):
                raise ValueError("rubric criteria must have different names")
        if self.apr_sections:
            names = [s.name.lower() for s in self.apr_sections]
            if len(names) != len(set(names)):
                raise ValueError("report sections must have different names")
        return self


class ExamControllerIn(BaseModel):
    """The Controller of Examinations on every notice; null: nobody chosen."""

    user_id: uuid.UUID | None


class NoticeBoardIn(BaseModel):
    """A notice for the notice board; no unit: the whole university."""

    unit_id: uuid.UUID | None = None
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    body: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] = ""
    pinned: bool = False
    ends_on: date | None = None  # off the board after this day


class NoticeBoardUpdate(BaseModel):
    title: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
        | None
    ) = None
    body: Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)] | None = None
    pinned: bool | None = None
    ends_on: date | None = None


class SupervisorChangeIn(BaseModel):
    """A proposed change of supervisor (supervisor_changes.py)."""

    to_faculty_id: uuid.UUID
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    scholar_consent: bool = False
    order_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )
    effective_on: date | None = None  # the order's date; else the day it is approved


class SupervisorChangeUpdate(BaseModel):
    to_faculty_id: uuid.UUID | None = None
    reason: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
        | None
    ) = None
    scholar_consent: bool | None = None
    order_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = (
        None
    )
    effective_on: date | None = None


class ModuleUpdate(BaseModel):
    enabled: bool


# --- notifications ----------------------------------------------------------------------


class OpenedIn(BaseModel):
    """A page the person opened, as a path: notifications pointing there are read."""

    link: Annotated[str, StringConstraints(min_length=1, max_length=500, pattern=r"^/")]


class UnreadOut(BaseModel):
    unread: int


class NotificationOut(Out):
    id: uuid.UUID
    category: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class EmailMutedIn(BaseModel):
    email_muted: list[MutableCategory] = Field(max_length=20)


class WhatsappIn(BaseModel):
    """Own number only; null clears it (opts out)."""

    whatsapp_number: Annotated[str, StringConstraints(pattern=WHATSAPP_NUMBER_RE)] | None
    whatsapp_muted: list[MutableCategory] = Field(max_length=20)


# --- files ------------------------------------------------------------------------------


class UploadIn(BaseModel):
    table_name: FileOwner
    record_id: uuid.UUID
    slot: FileSlot | None = None  # a named place on a scholar's record (PhD file)
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
    slot: FileSlot | None
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
    study_mode: StudyMode | None
    # Personal data: null unless `sees_personal` (scope.sees_personal), then null = not recorded.
    sees_personal: bool
    gender: Gender | None
    category: Category | None
    has_disability: bool | None
    father_name: str | None
    directory_only: bool = False  # an opened department reading another unit's scholar


class StandInIn(BaseModel):
    stand_in_id: uuid.UUID
    starts_on: date
    ends_on: date


class StandInOut(BaseModel):
    stand_in: Ref
    starts_on: date
    ends_on: date


class StandInFor(BaseModel):
    supervisor: Ref
    starts_on: date
    ends_on: date


class StandIns(BaseModel):
    """The caller's own stand-in (if any) and the supervisors they currently stand in for."""

    mine: StandInOut | None
    standing_in_for: list[StandInFor]


OrderRef = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class ScholarOwnProfile(BaseModel):
    """What a scholar fills in about themself; only while a field is still not recorded."""

    model_config = ConfigDict(extra="forbid")
    study_mode: StudyMode | None = None
    gender: Gender | None = None
    category: Category | None = None
    has_disability: bool | None = None
    father_name: Name | None = None


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
    study_mode: StudyMode | None = None
    gender: Gender | None = None
    category: Category | None = None
    has_disability: bool | None = None
    father_name: Name | None = None
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


class AppointmentOrderIn(BaseModel):
    """The order behind one appointment (Form IV), and a past one's end; null clears a value."""

    appointed_on: date | None = None
    order_ref: OrderRef | None = None
    ended_on: date | None = None  # only on a past appointment


class AppointmentOut(BaseModel):
    id: uuid.UUID
    role: SupervisionRole
    faculty: Ref
    appointed_on: date | None
    order_ref: str | None
    ended_on: date | None  # null: the current appointment


class SupervisionView(BaseModel):
    appointments: list[AppointmentOut]  # current first, then the latest ended
    can_manage: bool
    open_change: dict[str, Any] | None = None  # a change of supervisor under way
    can_propose_change: bool = False


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
    on_behalf_of: str | None = None
    step: str | None
    to: str | None
    comment: str | None
    rating: Rating | None
    at: datetime
    signature: str | None = None  # data: URL of the specimen that signed it (PRD F17b)


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
    # How this viewer's action is signed (PRD F17b): required by the university, optional (they
    # may choose to sign: signing is off but their signature is confirmed), or off.
    signing: Literal["required", "optional", "off"]
    send_back_targets: list[SendBackTarget]
    blocked_reason: str | None
    history: list[HistoryEntry]


class ThesisGateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    label: str
    met: bool
    detail: str


class NoDuesMine(BaseModel):
    required: bool  # university setting require_no_dues: the thesis waits for it
    item: ItemView | None


SigningCodeText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)]


class ApproveIn(BaseModel):
    comment: Comment | None = None
    rating: Rating | None = None  # required with the comment on assessed items (PRD F8)
    code: SigningCodeText | None = None  # while signing is required (PRD F17b)
    sign: bool = False  # sign anyway, while signing is not required


class SigningCodeIn(BaseModel):
    action: SigningAction


class SendBackIn(BaseModel):
    comment: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    to_step: int | None = Field(default=None, ge=0)
    code: SigningCodeText | None = None
    sign: bool = False


class QueueEntry(BaseModel):
    item_type: ItemType
    id: uuid.UUID
    label: str
    title: str
    scholar: Ref
    step: str
    waiting_since: datetime
    days_waiting: int
    quick_approve: bool


# --- progress reports -------------------------------------------------------------------

Summary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=20000)]


class SectionText(BaseModel):
    """One section of the template as the scholar filled it; blank is fine in a draft."""

    name: Name
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]


ReportSections = Annotated[list[SectionText], Field(max_length=10)]


class ReportIn(BaseModel):
    report_year: int = Field(ge=2000, le=2100)
    period: Period
    summary: Summary
    sections: ReportSections = []


class AssistantshipIn(BaseModel):
    assistantship: Assistantship | None  # null: not stated


class ReportUpdate(BaseModel):
    summary: Summary | None = None
    sections: ReportSections | None = None


class PeriodActivity(BaseModel):
    """What the system already holds for the report's six months (PRD F8)."""

    meetings: int
    publications: list[str] | None  # None: the module is off
    conferences: list[str] | None


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


LongTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class MilestoneIn(BaseModel):
    scholar_id: uuid.UUID
    milestone_type: MilestoneType
    status: MilestoneStatus = "Pending"
    approval_body: ApprovalBody
    resolution_number: Resolution | None = None
    resolution_date: date | None = None
    notes: Notes = ""
    approved_title: LongTitle | None = None


class MilestoneUpdate(BaseModel):
    milestone_type: MilestoneType | None = None
    status: MilestoneStatus | None = None
    approval_body: ApprovalBody | None = None
    resolution_number: Resolution | None = None
    resolution_date: date | None = None
    notes: Notes | None = None
    approved_title: LongTitle | None = None


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
    approved_title: str | None
    seminar_id: uuid.UUID | None  # the seminar whose recommendation opened this entry
    updated_at: datetime


# --- progress seminars ------------------------------------------------------------------

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Venue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class SeminarIn(BaseModel):
    unit_id: uuid.UUID
    kind: SeminarKind = "progress"
    title: Title
    starts_at: datetime
    venue: Venue = ""
    # The report period a progress seminar reviews; the other kinds have none.
    report_due: date | None = None
    report_year: int | None = Field(default=None, ge=2000, le=2100)
    period: Period | None = None
    notes: Notes = ""
    scholar_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    panel_faculty_ids: list[uuid.UUID] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def _report_only_for_progress(self) -> "SeminarIn":
        given = [self.report_due, self.report_year, self.period]
        if self.kind == "progress" and None in given:
            raise ValueError("a progress seminar needs the report due date, year and period")
        if self.kind != "progress" and any(v is not None for v in given):
            raise ValueError("only a progress seminar reviews a report period")
        return self


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


def _in_signing_order(signers: list[str] | None) -> list[str] | None:
    """Each signer once, in the order the paper notices sign (enums.NOTICE_SIGNERS)."""
    if signers is None:
        return None
    return sorted(set(signers), key=NOTICE_SIGNERS.index)


NoticeLine = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class NoticeIn(BaseModel):
    """The department admin's changes to one seminar's notice; null or left out: the default."""

    signers: list[NoticeSigner] | None = Field(default=None, min_length=1, max_length=6)
    announcement: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None
    ) = None
    closing: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    copy_to: list[NoticeLine] | None = Field(default=None, max_length=20)
    # Who signs in a role several people hold (the Exam Office, the admin, the head, the Dean).
    names: dict[NoticeSigner, uuid.UUID] | None = None

    @model_validator(mode="after")
    def _order(self) -> "NoticeIn":
        self.signers = _in_signing_order(self.signers)  # type: ignore[assignment]
        return self


class DepartmentSignersIn(BaseModel):
    """Who signs every seminar notice of the department; null: back to the default."""

    signers: list[NoticeSigner] | None = Field(default=None, min_length=1, max_length=6)
    names: dict[NoticeSigner, uuid.UUID] | None = None  # for all the department's notices

    @model_validator(mode="after")
    def _order(self) -> "DepartmentSignersIn":
        self.signers = _in_signing_order(self.signers)  # type: ignore[assignment]
        return self


class SeminarRow(BaseModel):
    id: uuid.UUID
    unit: Ref
    kind: SeminarKind
    title: str
    starts_at: datetime
    venue: str
    report_due: date | None
    report_year: int | None
    period: Period | None
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
    can_request: bool
    require_hardcopy: bool
    is_grader: bool
    can_attend: bool


class HardcopyIn(BaseModel):
    received_on: date | None


# --- seminar grading & to-dos -----------------------------------------------------------


class FormAnswerIn(BaseModel):
    question: FormQuestion
    answer: FormAnswer
    remark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""


class GradeIn(BaseModel):
    """Rubric `scores`, or, for a seminar marked by form questions, `answers` to every question
    and a `recommendation` (settings.seminar_forms)."""

    scores: dict[str, float] = Field(default_factory=dict, max_length=10)
    answers: list[FormAnswerIn] | None = Field(default=None, max_length=20)
    recommendation: SeminarRecommendation | None = None
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
    answers: list[FormAnswerIn] | None = None
    recommendation: SeminarRecommendation | None = None
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
    seminar_kind: SeminarKind
    scholar: Ref
    form: SeminarForm  # how this kind is marked here
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


# --- audit log ---------------------------------------------------------------------------


class AuditRow(BaseModel):
    """One audit entry as its readers see it: never the recorded values (routers/audit.py)."""

    id: uuid.UUID
    at: datetime
    actor: str | None  # None: the system, or a link used without a login
    actor_roles: list[str]
    action: AuditAction
    table_name: str
    record_id: str
    from_state: str | None
    to_state: str | None
    fields: list[str]  # columns an update changed
    scholar: Ref | None


# --- grievances (grievances.py) ----------------------------------------------------------


Statement = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class GrievanceIn(BaseModel):
    """A scholar's grievance (grievances.py)."""

    category: GrievanceCategory
    subject: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: Statement


class GrievanceDecisionIn(BaseModel):
    """The grievance cell's decision, or the appeal's, with its reasons."""

    text: Statement


class GrievanceAppealIn(BaseModel):
    reason: Statement


class GrievanceActions(BaseModel):
    decide: bool
    withdraw: bool
    accept: bool
    appeal: bool
    decide_appeal: bool
    attach: bool


class GrievanceView(BaseModel):
    id: uuid.UUID
    scholar: Ref
    category: GrievanceCategory
    subject: str
    description: str
    status: GrievanceStatus
    filed_at: datetime
    due_on: date | None  # the deadline of whoever must decide now
    decision: str | None
    decided_at: datetime | None
    decided_by: str | None
    appeal_closes_on: date | None  # the last day to appeal, while decided
    appeal_reason: str | None
    appealed_at: datetime | None
    appeal_decision: str | None
    appeal_decided_at: datetime | None
    appeal_decided_by: str | None
    appeals_to: str  # "the Ombudsperson" or "the Vice Chancellor"
    can: GrievanceActions
