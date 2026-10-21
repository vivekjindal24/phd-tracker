"""A small university for tests (TESTING.md §2):

Root (University)
├── School A  ── Dept A1, Dept A2
└── School B  ── Dept B1

One user per role, plus Meera: supervisor of scholar a1, HoD of A1 and admin of A1."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import hash_password
from app.models import Faculty, OrgUnit, RoleAssignment, Scholar, User
from app.org import create_unit

PASSWORD = "correct-horse-battery"
_HASH = hash_password(PASSWORD)  # argon2 is slow on purpose: hash once per session


@dataclass
class World:
    root: OrgUnit
    school_a: OrgUnit
    school_b: OrgUnit
    a1: OrgUnit
    a2: OrgUnit
    b1: OrgUnit
    root_admin: User
    research_office: User
    exam_office: User
    library: User
    dean_a: User
    hod_a2: User
    hod_b1: User
    admin_a1: User  # department admin (DRC coordinator) of A1
    meera: User  # supervisor of scholar_a1 + HoD A1 + admin A1
    sup_a2: User  # supervisor of scholar_a2
    sup_b1: User
    co_sup: User  # faculty in B1, co-supervisor of scholar_a1
    scholar_a1: User
    scholar_a1b: User  # second A1 scholar, supervised by sup_a2 (cross-unit supervisor)
    scholar_a2: User
    scholar_b1: User
    meera_faculty: Faculty
    sup_a2_faculty: Faculty
    sup_b1_faculty: Faculty
    co_sup_faculty: Faculty
    s_a1: Scholar
    s_a1b: Scholar
    s_a2: Scholar
    s_b1: Scholar


async def _user(session: AsyncSession, name: str) -> User:
    user = User(
        email=f"{name}@x.edu", full_name=name.replace("_", " ").title(), password_hash=_HASH
    )
    session.add(user)
    await session.flush()
    return user


async def _role(session: AsyncSession, user: User, role: str, unit: OrgUnit | None = None) -> None:
    session.add(RoleAssignment(user_id=user.id, role=role, unit_id=unit.id if unit else None))


async def _faculty(session: AsyncSession, user: User, unit: OrgUnit) -> Faculty:
    f = Faculty(user_id=user.id, unit_id=unit.id, designation="Professor", max_scholars=8)
    session.add(f)
    await session.flush()
    return f


async def _scholar(
    session: AsyncSession, user: User, unit: OrgUnit, roll: str, sup: Faculty, co: Faculty | None
) -> Scholar:
    s = Scholar(
        user_id=user.id,
        unit_id=unit.id,
        roll_number=roll,
        supervisor_id=sup.id,
        co_supervisor_id=co.id if co else None,
    )
    session.add(s)
    await session.flush()
    return s


async def build_world(session: AsyncSession) -> World:
    root = await create_unit(session, None, None, "Test University", "University", "TU")
    school_a = await create_unit(session, None, root, "School A", "School", "SA")
    school_b = await create_unit(session, None, root, "School B", "School", "SB")
    a1 = await create_unit(session, None, school_a, "Dept A1", "Department", "A1")
    a2 = await create_unit(session, None, school_a, "Dept A2", "Department", "A2")
    b1 = await create_unit(session, None, school_b, "Dept B1", "Department", "B1")

    names = [
        "root_admin",
        "research_office",
        "exam_office",
        "library",
        "dean_a",
        "hod_a2",
        "hod_b1",
        "admin_a1",
        "meera",
        "sup_a2",
        "sup_b1",
        "co_sup",
        "scholar_a1",
        "scholar_a1b",
        "scholar_a2",
        "scholar_b1",
    ]
    u = {n: await _user(session, n) for n in names}

    await _role(session, u["root_admin"], "admin", root)
    for office in ("research_office", "exam_office", "library"):
        await _role(session, u[office], office)
    await _role(session, u["dean_a"], "unit_head", school_a)
    await _role(session, u["hod_a2"], "unit_head", a2)
    await _role(session, u["hod_b1"], "unit_head", b1)
    await _role(session, u["admin_a1"], "admin", a1)
    await _role(session, u["meera"], "unit_head", a1)
    await _role(session, u["meera"], "admin", a1)

    meera_f = await _faculty(session, u["meera"], a1)
    sup_a2_f = await _faculty(session, u["sup_a2"], a2)
    sup_b1_f = await _faculty(session, u["sup_b1"], b1)
    co_f = await _faculty(session, u["co_sup"], b1)

    s_a1 = await _scholar(session, u["scholar_a1"], a1, "PHD-A1-001", meera_f, co_f)
    s_a1b = await _scholar(session, u["scholar_a1b"], a1, "PHD-A1-002", sup_a2_f, None)
    s_a2 = await _scholar(session, u["scholar_a2"], a2, "PHD-A2-001", sup_a2_f, None)
    s_b1 = await _scholar(session, u["scholar_b1"], b1, "PHD-B1-001", sup_b1_f, None)
    await session.flush()

    return World(
        root=root,
        school_a=school_a,
        school_b=school_b,
        a1=a1,
        a2=a2,
        b1=b1,
        **u,
        meera_faculty=meera_f,
        sup_a2_faculty=sup_a2_f,
        sup_b1_faculty=sup_b1_f,
        co_sup_faculty=co_f,
        s_a1=s_a1,
        s_a1b=s_a1b,
        s_a2=s_a2,
        s_b1=s_b1,
    )


def ids(users: list[User]) -> set[uuid.UUID]:
    return {x.id for x in users}
