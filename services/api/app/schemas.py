"""Pydantic boundary models. Literals come from app/enums.py, mirroring the DB CHECKs."""

import uuid
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.enums import (
    AssignedRole,
    CoSupervision,
    Designation,
    ItemType,
    ModuleKey,
    NotificationCategory,
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
