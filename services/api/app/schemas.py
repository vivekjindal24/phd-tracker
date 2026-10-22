"""Pydantic boundary models. Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    AssignedRole,
    CoSupervision,
    Designation,
    FileOwner,
    ItemState,
    ItemType,
    MeetingShare,
    ModuleKey,
    NotificationCategory,
    Period,
    Stage,
    StepKind,
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
    password: Password
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


class SettingsOut(BaseModel):
    co_supervision: CoSupervision
    modules: dict[ModuleKey, bool]
    chains: dict[ItemType, list[ChainStep]]


class SettingsUpdate(BaseModel):
    co_supervision: CoSupervision


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
