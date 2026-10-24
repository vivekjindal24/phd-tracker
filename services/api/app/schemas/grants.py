"""Boundary models of the grants modules: fellowships, research projects and the grant ledger
with utilisation certificates (PRD M6-M8)."""

import uuid
from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.enums import FellowshipScheme, FellowshipStatus, LedgerHead, LedgerKind, ProjectStatus
from app.schemas import LongTitle, Notes, Ref, Resolution

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MonthlyAmount = Annotated[float, Field(ge=0, le=10_000_000)]
Amount = Annotated[float, Field(gt=0, le=10_000_000_000)]


def _ordered(start: date | None, end: date | None, what: str = "end date") -> None:
    if start and end and end < start:
        raise ValueError(f"the {what} is before the start")


# --- fellowships ----------------------------------------------------------------------------


class FellowshipIn(BaseModel):
    scholar_id: uuid.UUID
    scheme: FellowshipScheme
    amount_monthly: MonthlyAmount
    hra_amount: MonthlyAmount = 0
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self) -> "FellowshipIn":
        _ordered(self.start_date, self.end_date)
        return self


class FellowshipUpdate(BaseModel):
    """`srf_upgrade_on` records the JRF→SRF upgrade (UX Flow 11); dates are re-checked
    against the stored row in the router."""

    scheme: FellowshipScheme | None = None
    amount_monthly: MonthlyAmount | None = None
    hra_amount: MonthlyAmount | None = None
    start_date: date | None = None
    end_date: date | None = None
    srf_upgrade_on: date | None = None
    status: FellowshipStatus | None = None


class FellowshipOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    roll_number: str
    unit: Ref
    scheme: FellowshipScheme
    amount_monthly: float
    hra_amount: float
    start_date: date
    end_date: date
    srf_upgrade_on: date | None
    status: FellowshipStatus
    can_manage: bool
    sees_ledger: bool


# --- projects -------------------------------------------------------------------------------


class ProjectIn(BaseModel):
    pi_id: uuid.UUID  # a faculty id
    unit_id: uuid.UUID | None = None  # defaults to the PI's unit
    agency: Short
    title: LongTitle
    sanction_number: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    amount_sanctioned: Annotated[float, Field(ge=0, le=10_000_000_000)]
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self) -> "ProjectIn":
        _ordered(self.start_date, self.end_date)
        return self


class ProjectUpdate(BaseModel):
    agency: Short | None = None
    title: LongTitle | None = None
    sanction_number: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
        | None
    ) = None
    amount_sanctioned: Annotated[float, Field(ge=0, le=10_000_000_000)] | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: ProjectStatus | None = None


class MemberIn(BaseModel):
    scholar_id: uuid.UUID
    member_role: Short = "Research scholar"


class MemberOut(BaseModel):
    id: uuid.UUID
    scholar: Ref
    roll_number: str
    member_role: str


class ProjectOut(BaseModel):
    id: uuid.UUID
    title: str
    agency: str
    sanction_number: str
    amount_sanctioned: float
    start_date: date
    end_date: date
    status: ProjectStatus
    pi: Ref  # the faculty id and name
    unit: Ref
    members: list[MemberOut]
    can_manage: bool
    sees_ledger: bool


# --- ledger and utilisation certificates ----------------------------------------------------


class LedgerEntryIn(BaseModel):
    project_id: uuid.UUID | None = None
    fellowship_id: uuid.UUID | None = None
    entry_kind: LedgerKind
    head: LedgerHead
    amount: Amount
    entry_date: date
    reference: Resolution | None = None
    note: Notes = ""

    @model_validator(mode="after")
    def _one_owner(self) -> "LedgerEntryIn":
        if (self.project_id is None) == (self.fellowship_id is None):
            raise ValueError("give exactly one of project_id or fellowship_id")
        return self


class LedgerRow(BaseModel):
    id: uuid.UUID
    entry_kind: LedgerKind
    head: LedgerHead
    amount: float
    entry_date: date
    reference: str | None
    note: str
    balance: float  # running balance after this entry


class LedgerView(BaseModel):
    entries: list[LedgerRow]
    received: float
    spent: float
    balance: float
    sanctioned: float | None  # projects only
    can_manage: bool  # add disbursements and expenses, remove entries
    can_add_expense: bool  # the PI on their own project


class UcIn(BaseModel):
    period_start: date
    period_end: date
    submitted_on: date | None = None

    @model_validator(mode="after")
    def _dates(self) -> "UcIn":
        _ordered(self.period_start, self.period_end, "period end")
        return self


class UcUpdate(BaseModel):
    submitted_on: date | None


class UcOut(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date
    submitted_on: date | None
