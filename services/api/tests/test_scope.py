"""Visibility at every level of the tree (SECURITY.md §2, TESTING.md §1.2)."""

import pytest
from sqlalchemy import select, update

from app import scope
from app.auth.principal import load_principal
from app.errors import ApiError
from app.models import Scholar, Settings


async def visible_rolls(session, user) -> set[str]:
    principal = await load_principal(session, user)
    rows = await session.scalars(
        select(Scholar.roll_number).where(scope.scholar_predicate(principal, "scholars"))
    )
    return set(rows)


ALL = {"PHD-A1-001", "PHD-A1-002", "PHD-A2-001", "PHD-B1-001"}


async def test_scholar_sees_only_self(session, world):
    assert await visible_rolls(session, world.scholar_a1) == {"PHD-A1-001"}


async def test_supervisor_sees_only_supervisees_across_units(session, world):
    # sup_a2 sits in A2 but supervises an A1 scholar too.
    assert await visible_rolls(session, world.sup_a2) == {"PHD-A1-002", "PHD-A2-001"}


async def test_hod_sees_own_department_only(session, world):
    assert await visible_rolls(session, world.hod_a2) == {"PHD-A2-001"}
    assert await visible_rolls(session, world.hod_b1) == {"PHD-B1-001"}


async def test_dean_sees_whole_school_not_other_schools(session, world):
    assert await visible_rolls(session, world.dean_a) == {"PHD-A1-001", "PHD-A1-002", "PHD-A2-001"}


async def test_department_admin_sees_department(session, world):
    assert await visible_rolls(session, world.admin_a1) == {"PHD-A1-001", "PHD-A1-002"}


async def test_root_admin_and_offices_see_everyone(session, world):
    for user in (world.root_admin, world.research_office, world.exam_office, world.library):
        assert await visible_rolls(session, user) == ALL


async def test_multi_role_user_gets_union_of_roles(session, world):
    # Meera: supervisor of PHD-A1-001 + HoD/admin of A1 -> exactly A1, nothing from A2/B1.
    assert await visible_rolls(session, world.meera) == {"PHD-A1-001", "PHD-A1-002"}


async def test_co_supervisor_sees_nothing_while_setting_is_off(session, world):
    assert await visible_rolls(session, world.co_sup) == set()


@pytest.mark.parametrize("mode", ["view", "approve"])
async def test_co_supervisor_sees_co_supervised_scholar_when_enabled(session, world, mode):
    await session.execute(update(Settings).values(co_supervision=mode))
    await session.commit()
    assert await visible_rolls(session, world.co_sup) == {"PHD-A1-001"}


async def test_out_of_scope_is_403_not_404(session, world):
    principal = await load_principal(session, world.hod_b1)
    with pytest.raises(ApiError) as exc:
        await scope.get_scholar_or_403(session, principal, world.s_a1.id)
    assert exc.value.status == 403
    # A non-existent id looks exactly the same: existence is never leaked.
    with pytest.raises(ApiError) as missing:
        await scope.get_scholar_or_403(session, principal, world.root.id)
    assert missing.value.status == 403


async def test_soft_deleted_scholar_is_invisible_even_to_offices(session, world):
    await session.execute(
        update(Scholar).where(Scholar.id == world.s_b1.id).values(deleted_at=Scholar.created_at)
    )
    await session.commit()
    principal = await load_principal(session, world.research_office)
    with pytest.raises(ApiError):
        await scope.get_scholar_or_403(session, principal, world.s_b1.id)
