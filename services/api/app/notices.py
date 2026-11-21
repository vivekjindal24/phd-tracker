"""The notices of seminars and vivas (PRD F17b): Anveshan's wording, who signs, and the
department admin's changes — for every seminar or viva of the department, or for one (owner,
2026-11-21). The forms themselves are drawn in phd_forms.py."""

import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import committee
from app.auth.principal import Principal
from app.crud import update
from app.enums import LOCAL_TZ, NOTICE_SIGNER_LABELS, OFFICE_ROLES, SEMINAR_KIND_LABELS
from app.errors import ApiError
from app.models import (
    CommitteeFormation,
    OrgUnit,
    RoleAssignment,
    Scholar,
    Seminar,
    Settings,
    User,
    VivaArrangement,
)

Kind = Literal["seminar", "viva"]
Record = Seminar | VivaArrangement

DEFAULT_SIGNERS: dict[Kind, tuple[str, ...]] = {
    "seminar": ("admin", "unit_head", "dean"),
    "viva": ("exam_office", "unit_head", "dean"),
}
# Who a notice is copied to, until the university's own list is a setting (F17, part 4).
COPY_TO: dict[Kind, list[str]] = {
    "seminar": [
        "The Vice Chancellor",
        "The Dean of the Faculty",
        "The Research Office",
        "The supervisor and the members of the Research Advisory Committee",
        "The scholar",
    ],
    "viva": [
        "The Vice Chancellor",
        "The Dean of the Faculty",
        "The Head of the Department",
        "The Research Office",
        "The members of the Examination Board",
        "The scholar",
    ],
}
UNIT_COLUMN = {"seminar": OrgUnit.notice_signers, "viva": OrgUnit.viva_notice_signers}


def signer(name: str | None, role: str, signature: str | None = None) -> dict[str, Any]:
    return {"name": name or "", "role": role, "signature": signature}


# The signers named from who holds a role; the others come from the department's committee.
ROLE_SIGNERS = ("exam_office", "admin", "unit_head", "dean")


async def holders(
    session: AsyncSession, unit_id: uuid.UUID | None, role: str
) -> list[dict[str, str]]:
    """Everyone who holds a role today — a unit's head or admin, or an office (the Exam Office)."""
    if role in OFFICE_ROLES:
        where = RoleAssignment.unit_id.is_(None)
    elif unit_id is None:
        return []
    else:
        where = RoleAssignment.unit_id == unit_id
    rows = await session.execute(
        select(User.id, User.full_name)
        .join(RoleAssignment, RoleAssignment.user_id == User.id)
        .where(
            where,
            RoleAssignment.role == role,
            RoleAssignment.deleted_at.is_(None),
            User.deleted_at.is_(None),
        )
        .distinct()
        .order_by(User.full_name)
    )
    return [{"id": str(uid), "name": name} for uid, name in rows]


async def holder(session: AsyncSession, unit_id: uuid.UUID | None, role: str) -> str | None:
    """The one person who holds a role. None when nobody or several do: a form then prints the
    role alone rather than guess who signs (owner, 2026-11-22)."""
    found = await holders(session, unit_id, role)
    return found[0]["name"] if len(found) == 1 else None


def kind_of(record: Record) -> Kind:
    return "seminar" if isinstance(record, Seminar) else "viva"


def name(record: Record) -> str:
    if isinstance(record, VivaArrangement):
        return "Viva-Voce Examination"
    label = SEMINAR_KIND_LABELS[record.kind].replace(" seminar", " Seminar")
    return label.replace("Pre-synopsis", "Pre-Thesis Synopsis")


async def standard(session: AsyncSession, record: Record) -> dict[str, Any]:
    """The standard wording, before the department admin's changes: Anveshan's, with the
    university's "copy to" list for this kind of notice (settings.phd_forms)."""
    names = await session.scalar(select(Settings.phd_forms)) or {}
    key = f"{record.kind}_notice" if isinstance(record, Seminar) else "viva_notice"
    seminar = isinstance(record, Seminar)
    when = (record.starts_at if seminar else record.scheduled_at).astimezone(LOCAL_TZ)
    at = f"{when:%I:%M %p}".lstrip("0")  # 4:30 PM, as the paper notices read
    link = None if seminar else record.online_link
    return {
        "announcement": (
            f"This is for your kind information that the {name(record)} of the following "
            f"research scholar has been scheduled on {when:%d %B %Y} ({when:%A}) at {at}"
            + (f" in {record.venue}." if record.venue else ".")
            + (f" It may also be joined online at {link}." if link else "")
        ),
        "closing": f"All are cordially invited to attend the {name(record)}.",
        "copy_to": (names.get(key) or {}).get("copy_to") or COPY_TO[kind_of(record)],
    }


async def printed(session: AsyncSession, record: Record) -> dict[str, Any]:
    """The wording as printed: the standard one, with the department admin's changes."""
    custom = {k: v for k, v in (record.notice or {}).items() if v}
    return {**await standard(session, record), **custom}


async def unit_of(session: AsyncSession, record: Record) -> uuid.UUID:
    """The department whose notices these are: the seminar's, or the scholar's for a viva."""
    if isinstance(record, Seminar):
        return record.unit_id
    return await session.scalar(select(Scholar.unit_id).where(Scholar.id == record.scholar_id))


async def department_signers(session: AsyncSession, record: Record) -> list[str]:
    kind = kind_of(record)
    unit = await session.scalar(
        select(UNIT_COLUMN[kind]).where(OrgUnit.id == await unit_of(session, record))
    )
    return list(unit or DEFAULT_SIGNERS[kind])


async def signer_keys(session: AsyncSession, record: Record) -> list[str]:
    """Who signs: as set for this seminar or viva, else for its department, else the default."""
    custom = (record.notice or {}).get("signers")
    return list(custom) if custom else await department_signers(session, record)


async def candidates(session: AsyncSession, record: Record) -> dict[str, list[dict[str, str]]]:
    """Who holds each role a notice may be signed in, checked afresh before every print."""
    unit = await unit_of(session, record)
    parent = await session.scalar(select(OrgUnit.parent_id).where(OrgUnit.id == unit))
    return {
        "exam_office": await holders(session, None, "exam_office"),
        "admin": await holders(session, unit, "admin"),
        "unit_head": await holders(session, unit, "unit_head"),
        "dean": await holders(session, parent, "unit_head"),
    }


async def department_signer(session: AsyncSession, unit_id: uuid.UUID, key: str) -> str | None:
    """Who signs a department's other forms in a role (the Dean on the appointment of a
    supervisor, on the formation of a committee): the person the department chose on its
    Notice card, while they still hold the role; else the only one who holds it; else nobody,
    and the line prints with the role alone (owner, 2026-11-22)."""
    unit = await session.get(OrgUnit, unit_id)
    if unit is None:
        return None
    on = unit.parent_id if key == "dean" else unit.id
    people = await holders(session, on, "unit_head" if key == "dean" else key)
    pick = (unit.notice_names or {}).get(key)
    match = next((p["name"] for p in people if p["id"] == pick), None)
    return match or (people[0]["name"] if len(people) == 1 else None)


async def department_names(session: AsyncSession, record: Record) -> dict[str, str]:
    unit = await unit_of(session, record)
    return await session.scalar(select(OrgUnit.notice_names).where(OrgUnit.id == unit)) or {}


async def chosen(
    session: AsyncSession, record: Record, held: dict[str, list[dict[str, str]]]
) -> dict[str, str | None]:
    """The person who signs in each role: the one chosen for this seminar or viva, else for the
    department — the Controller of Examinations once for the whole university — only while
    they still hold the role, else the only one who holds it. None when several hold it and none
    is chosen: the line then prints with the role alone."""
    names = {**await department_names(session, record), **(record.notice or {}).get("names", {})}
    controller = await session.scalar(select(Settings.exam_controller_id))
    names["exam_office"] = str(controller) if controller else None
    out: dict[str, str | None] = {}
    for key, people in held.items():
        ids = {p["id"] for p in people}
        pick = names.get(key)
        out[key] = pick if pick in ids else (people[0]["id"] if len(people) == 1 else None)
    return out


async def signers(session: AsyncSession, record: Record) -> list[dict[str, Any]]:
    """Each signer named from the records; one person holding two of the roles signs once, with
    both ("Head of Department & Chairperson, DRC", as the paper notices read)."""
    keys = await signer_keys(session, record)
    unit = await unit_of(session, record)
    drc: list[dict[str, Any]] = []
    if {"drc_chair", "drc_secretary"} & set(keys):
        current = await committee.current(session, CommitteeFormation.unit_id == unit)
        drc = await committee.members(session, current.id) if current else []
    held = await candidates(session, record)
    picks = await chosen(session, record, held)

    async def named(key: str) -> str | None:
        if key in ("drc_chair", "drc_secretary"):
            role = "chairperson" if key == "drc_chair" else "secretary"
            return next((m["name"] for m in drc if m["role"] == role), None)
        return next((p["name"] for p in held[key] if p["id"] == picks[key]), None)

    out: list[dict[str, Any]] = []
    for key in keys:
        who, role = await named(key), NOTICE_SIGNER_LABELS[key]
        same = next((o for o in out if who and o["name"] == who), None)
        if same:
            same["role"] += f" & {role}"
        else:
            out.append(signer(who, role))
    return out


async def view(
    session: AsyncSession, record: Record, can_edit: bool, can_set_controller: bool = False
) -> dict[str, Any]:
    """The Notice card: who signs, the department's signers, this record's changes, and
    Anveshan's wording beneath them."""
    keys = await signer_keys(session, record)
    held = await candidates(session, record)
    picks = await chosen(session, record, held)
    return {
        "can_edit": can_edit,
        "choices": [{"key": k, "label": v} for k, v in NOTICE_SIGNER_LABELS.items()],
        "signers": keys,
        "department_signers": await department_signers(session, record),
        "custom": record.notice or {},
        "standard": await standard(session, record),
        "holders": held,  # who holds each role a notice is signed in
        "names": picks,  # who signs in each, as things stand
        # Signers several people could be and nobody is chosen for: printed with the role alone.
        "unnamed": [k for k in keys if k in held and len(held[k]) > 1 and picks[k] is None],
        # The Exam Office and the root admin choose the Controller of Examinations here too.
        "can_set_controller": can_set_controller,
    }


def sets_controller(principal: Principal) -> bool:
    """Who chooses the Controller of Examinations for the whole university (owner, 2026-11-22)."""
    return principal.is_root_admin or "exam_office" in principal.office_roles


async def set_controller(
    session: AsyncSession, principal: Principal, user_id: uuid.UUID | None
) -> None:
    """The Controller of Examinations named on every notice: someone in the Exam Office."""
    if user_id is not None:
        office = await holders(session, None, "exam_office")
        if str(user_id) not in {p["id"] for p in office}:
            raise ApiError(422, "not_a_holder", "That person is not in the Exam Office.")
    row = await session.get(Settings, 1)
    await update(session, principal, row, {"exam_controller_id": user_id})


async def _check_names(
    session: AsyncSession, record: Record, names: dict[str, str] | None
) -> dict[str, str]:
    """A chosen signer must hold that role today. The Controller of Examinations is chosen once
    for the university (settings), never per department or notice."""
    if "exam_office" in (names or {}):
        raise ApiError(
            422,
            "controller_is_university_wide",
            "The Controller of Examinations is chosen once for the whole university, by the "
            "Exam Office or the root admin.",
        )
    held = await candidates(session, record)
    for key, uid in (names or {}).items():
        if key not in held or uid not in {p["id"] for p in held[key]}:
            raise ApiError(
                422,
                "not_a_holder",
                f"That person does not hold the role of {NOTICE_SIGNER_LABELS[key]}.",
            )
    return dict(names or {})


async def change(
    session: AsyncSession, principal: Principal, record: Record, changes: dict[str, Any]
) -> None:
    """This seminar's or viva's notice only; what is left empty follows the department."""
    changes = {**changes, "names": await _check_names(session, record, changes.get("names"))}
    custom = {k: v for k, v in changes.items() if v}
    await update(session, principal, record, {"notice": custom or None})


async def change_department(
    session: AsyncSession,
    principal: Principal,
    record: Record,
    keys: list[str] | None,
    names: dict[str, str] | None = None,
) -> None:
    """Who signs every notice of this kind in the department, unless one says otherwise; and
    who signs in a role several people hold, for all its notices (seminars and vivas alike)."""
    checked = await _check_names(session, record, names)
    unit = await session.get(OrgUnit, await unit_of(session, record))
    column = UNIT_COLUMN[kind_of(record)].key
    await update(
        session, principal, unit, {column: keys, "notice_names": {**unit.notice_names, **checked}}
    )
